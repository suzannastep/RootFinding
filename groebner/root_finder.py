import numpy as np
import itertools
import warnings
from groebner.polynomial import MultiCheb, MultiPower
from groebner.Macaulay import Macaulay
from groebner.TelenVanBarel import TelenVanBarel
from groebner.gsolve import F4
from groebner.utils import Term, get_var_list, divides, TVBError, InstabilityWarning, match_size

'''
This module contains the tools necessary to find the points of the variety of the
ideal generated by a Groebner basis.
'''

def roots(polys, method = 'Groebner'):
    '''
    Finds the roots of the given list of polynomials.
    parameters
    ----------
    polys : list of polynomial objects
        Polynomials to find the common roots of.
    method : string
        The root finding method to be used. Can be either 'Groebner',
        'Macaulay', or 'TVB'.
    returns
    -------
    list of numpy arrays
        the common roots of the polynomials
    '''
    # Determine polynomial type
    poly_type = ''
    if (all(isinstance(p,MultiCheb) for p in polys)):
        poly_type = 'MultiCheb'
    elif (all(isinstance(p,MultiPower) for p in polys)):
        poly_type = 'MultiPower'
    else:
        raise ValueError('All polynomials must be the same type')

    if method == 'TVB':
        try:
            m_f, var_dict = TVBMultMatrix(polys, poly_type)
        except TVBError as e:
            if str(e) == "Doesn't have all x^n's on diagonal. Do linear transformation":
                raise e
                ''' #Optionally have it do F4 instead in thise case.
                warnings.warn("TVB method failed. Trying F4 instead. \
                    Error message from TVB is - {}".format(e), InstabilityWarning)
                method = 'Groebner'
                GB, m_f, var_dict = groebnerMultMatrix(polys, poly_type, method)
                '''
            elif str(e) == 'Polys are non-zero dimensional':
                return -1
            else:
                raise e
    else:
        GB, m_f, var_dict = groebnerMultMatrix(polys, poly_type, method)

    # both TVBMultMatrix and groebnerMultMatrix will return m_f as
    # -1 if the ideal is not zero dimensional or if there are no roots
    if type(m_f) == int:
        return -1

    # Get list of indexes of single variables and store vars that were not
    # in the vector space basis.
    dim = max(f.dim for f in polys)
    var_list = get_var_list(dim)
    var_indexes = [-1]*dim
    vars_not_in_basis = {}
    for i in range(len(var_list)):
        var = var_list[i] # x_i
        if var in var_dict:
            var_indexes[i] = var_dict[var]
        else:
            # maps the position in the root to its variable
            vars_not_in_basis[i] = var

    vnib = False
    if len(vars_not_in_basis) != 0:
        if method == 'TVB':
            print("This isn't working yet...")
            return -1
        vnib = True

    # Get left eigenvectors
    
    e = np.linalg.eig(m_f.T)
    eig = e[1]
    num_vectors = eig.shape[1]
        
    eig_vectors = [eig[:,i] for i in range(num_vectors)] # columns of eig
    roots = []
    for v in eig_vectors:
        if v[var_dict[tuple(0 for i in range(dim))]] == 0:
            continue
        root = np.zeros(dim, dtype=complex)
        # This will always work because var_indexes and root have the
        # same length - dim - and var_indexes has the variables in the
        # order they should be in the root
        for i in range(dim):
            x_i_pos = var_indexes[i]
            if x_i_pos != -1:
                root[i] = v[x_i_pos]/v[var_dict[tuple(0 for i in range(dim))]]
        if vnib:
            # Go through the indexes of variables not in the basis in
            # decreasing order. It must be done in decreasing order for the
            # roots to be calculated correctly, since the vars with lower
            # indexes depend on the ones with higher indexes
            for pos in list(vars_not_in_basis.keys())[::-1]:
                GB_poly = _get_poly_with_LT(vars_not_in_basis[pos], GB)
                var_value = GB_poly.evaluate_at(root) * -1
                root[pos] = var_value
        roots.append(root)
        #roots.append(newton_polish(polys,root))
    return roots

def groebnerMultMatrix(polys, poly_type, method):
    '''
    Called by the main roots function to calculate the multiplication matrix
    if we are using the f4 Groebner or Macaulay implementation. It returns
    everything that the roots function needs to proceed with the root finding
    calculations.
    Returns
    -------
        GB : list of polynomial objects
            The calculated groebner basis.
        m_f : 2D numpy array
            the multiplication matrix for a random polynomial f
        var_dict : dictionary of tuples to ints
            maps the variable to its location in the vector space basis, so if
            VB is [1, x, y, xy] then var_dict is {(1,0):1, (0,1):2}
    '''
    # Calculate groebner basis
    if method == 'Groebner':
        #G = Groebner(polys)
        #GB = G.solve()
        GB = F4(polys)
    else:
        GB = Macaulay(polys)

    dim = max(g.dim for g in GB) # dimension of the polynomials

    # Get the random polynomial and check for finitely many solutions
    f, var_list = _random_poly(poly_type, dim)

    if not _finitelyManySolutions(GB, var_list):
        return (-1,-1,-1)

    # Get the vector space basis
    VB, var_dict = vectorSpaceBasis(GB)

    # Make the multiplication matrix
    m_f = multMatrix(f, GB, VB)

    return GB, m_f, var_dict

def sortVB(VB):
    '''Sorts the Vector Basis into degrevlex order so the eigensolve is faster (in theory).
    
    Parameters
    ----------
    VB : numpy array
        Each row in VB is a term in the vector basis.
    
    Returns
    -------
    VB : numpy array
        The vector basis sorted so the lowest terms are at the top.
    '''
    VBList = list()
    for i in VB:
        VBList.append(Term(i))

    return VB[np.argsort(VBList)]

def TVBMultMatrix(polys, poly_type):
    '''
    Finds the multiplication matrix using the reduced Macaulay matrix from the
    TVB method.

    Parameters
    ----------
    polys : array-like
        The polynomials to find the common zeros of
    poly_type : string
        The type of the polynomials in polys

    Returns
    -------
    multiplicationMatrix : 2D numpy array
        The multiplication matrix for a random polynomial f
    var_dict : dictionary
        Maps each variable to its position in the vector space basis
    '''
    basisDict, VB, degree = TelenVanBarel(polys, run_checks = True)
        
    VB = sortVB(VB)

    dim = max(f.dim for f in polys)

    # Get random polynomial f
    f = _random_poly(poly_type, dim)[0]

    slices = list()
    for i in range(len(VB[0])):
        slices.append(VB.T[i])
    
    VBset = set()
    for mon in VB:
        VBset.add(tuple(mon))
        
    # Build multiplication matrix m_f
    mMatrix = np.zeros((len(VB), len(VB)))
    remainder = np.zeros([degree]*dim)
    
    for i in range(VB.shape[0]):
        f_coeff = f.mon_mult(VB[i], returnType = 'Matrix')
        for term in zip(*np.where(f_coeff != 0)):
            if term in VBset:
                remainder[term] += f_coeff[term]
            else:
                remainder[slices] -= f_coeff[term]*basisDict[term][slices]
        mMatrix[:,i] = remainder[slices]
        remainder[slices] = 0

    # Construct var_dict
    var_dict = {}
    for i in range(len(VB)):
        mon = VB[i]
        if np.sum(mon) == 1 or np.sum(mon) == 0:
            var_dict[tuple(mon)] = i
        
    return mMatrix, var_dict

def _finitelyManySolutions(GB, var_list):
    '''Returns true if the number of solutions N satisfies 1 <= N < infinity'''

    # Check for no solutions
    if len(GB) == 1 and all([i==1 for i in GB[0].coeff.shape]):
        print("No solutions")
        return False

    # Check for infinitely many solutions
    if not _test_zero_dimensional(var_list, GB):
        print("Ideal is not zero-dimensional; cannot calculate roots.")
        return False

    return True

def sorted_polys_coeff(polys):
    '''
    Sorts the polynomials by how much bigger the leading coefficient is than the rest of the coeff matrix.
    '''
    lead_coeffs = list()
    for poly in polys:
        lead_coeffs.append(np.abs(poly.lead_coeff)/np.sum(np.abs(poly.coeff))) #The lead_coeff to other stuff ratio.
    argsort_list = sorted(range(len(lead_coeffs)), key=lead_coeffs.__getitem__)[::-1]
    sorted_polys = list()
    for i in argsort_list:
        sorted_polys.append(polys[i])
    return sorted_polys

def multMatrix(poly, GB, basisList):
    '''
    Finds the matrix of the linear operator m_f on A = C[x_1,...,x_n]/I
    where f is the polynomial argument. The linear operator m_f is defined
    as m_f([g]) = [f]*[g] where [f] represents the coset of f in
    A. Since m_f is a linear operator on A, it can be represented by its
    matrix with respect to the vector space basis.
    parameters
    ----------
    poly : polynomial object
        The polynomial f for which to find the matrix m_f.
    GB: list of polynomial objects
        Polynomials that make up a Groebner basis for the ideal
    basisList : list of tuples
        The monomials that make up a basis for the vector space A
    returns
    -------
    multMatrix : square numpy array
        The matrix m_f
    '''
    basisSet = set(basisList)
    basisTerms = np.vstack(basisList)

    slices = list()
    for i in range(len(basisTerms[0])):
        slices.append(basisTerms.T[i])
    
    GB = sorted_polys_coeff(GB)

    # All polys in GB will be in the same dimension, so just match poly with
    # the first Groebner basis element
    poly = _match_poly_dim(poly, GB[0])[0]
    dim = len(basisList) # Dimension of the vector space basis
    
    multMatrix = np.zeros((dim, dim))
    for i in range(dim):
        monomial = basisList[i]
        poly_ = poly.mon_mult(monomial)
        multMatrix[:,i] = coordinateVector(poly_, GB, basisSet, slices)

    return multMatrix
    
def vectorSpaceBasis(GB):
    '''
    parameters
    ----------
    GB: list
        polynomial objects that make up a Groebner basis for the ideal
    returns
    -------
    basis : list
        tuples representing the monomials in the vector space basis
    var_to_pos_dict : dictionary
        maps each variable to its position in the vector space basis
    '''
    LT_G = [f.lead_term for f in GB]
    possibleVarDegrees = [range(max(tup)) for tup in zip(*LT_G)]
    possibleMonomials = itertools.product(*possibleVarDegrees)
    basis = []
    var_to_pos_dict = {}
    for mon in possibleMonomials:
        divisible = False
        for LT in LT_G:
            if divides(LT, mon):
                 divisible = True
                 break
        if not divisible:
            basis.append(mon)
            if (sum(mon) == 1) or (sum(mon) == 0):
                var_to_pos_dict[mon] = basis.index(mon)

    return basis, var_to_pos_dict

def coordinateVector(poly, GB, basisSet, slices):
    '''
    parameters
    ----------
    reducedPoly : polynomial object
        The polynomial for which to find the coordinate vector of its coset.
    GB : list of polynomial objects
        Polynomials that make up a Groebner basis for the ideal
    basisSet : set of tuples
        The monomials that make up a basis for the vector space
    slices : A list of np.arrays
        Contains the inexes of the vector basis so those spots can be pulled out of he coeff matrix quickly.
    returns
    -------
    coordinateVector : numpy array
        The coordinate vector of the given polynomial's coset in
        A = C[x_1,...x_n]/I as a vector space over C
    '''

    poly_coeff = reduce_poly(poly, GB, basisSet)
    return poly_coeff[slices]

def reduce_poly(poly, divisors, basisSet, permitted_round_error=1e-10):
    '''
    Divides a polynomial by a set of divisor polynomials using the standard
    multivariate division algorithm and returns the remainder
    parameters
    ----------
    poly : polynomial object
        the polynomial to be divided by the Groebner basis
    divisors : list of polynomial objects
        polynomials to divide poly by
    basisSet : set of tuples
        The monomials that make up a basis for the vector space
    returns
    -------
    polynomial object
        the remainder of poly / divisors
    '''
    remainder_shape = np.maximum.reduce([p.shape for p in divisors])
    remainder = np.zeros(remainder_shape)

    for term in zip(*np.where(poly.coeff != 0)):
        if term in basisSet:
            remainder[term] += poly.coeff[term]
            poly.coeff[term] = 0
    poly.__init__(poly.coeff, clean_zeros = False)

    # while poly is not the zero polynomial
    while np.any(poly.coeff):
        divisible = False
        # Go through polynomials in set of divisors
        for divisor in divisors:
            poly, divisor = _match_poly_dim(poly, divisor)
            # If the LT of the divisor divides the LT of poly
            if divides(divisor.lead_term, poly.lead_term):
                # Get the quotient LT(poly)/LT(divisor)
                LT_quotient = np.subtract(poly.lead_term, divisor.lead_term)

                poly_to_subtract_coeff = divisor.mon_mult(LT_quotient, returnType = 'Matrix')
                # Match sizes of poly_to_subtract and poly so
                # poly_to_subtract.coeff can be subtracted from poly.coeff
                poly_coeff, poly_to_subtract_coeff = match_size(poly.coeff, poly_to_subtract_coeff)
                new_coeff = poly_coeff - \
                    (poly.lead_coeff/poly_to_subtract_coeff[tuple(divisor.lead_term+LT_quotient)])*poly_to_subtract_coeff

                new_coeff[np.where(np.abs(new_coeff) < permitted_round_error)]=0

                for term in zip(*np.where(new_coeff != 0)):
                    if term in basisSet:
                        remainder[term] += new_coeff[term]
                        new_coeff[term] = 0

                poly.__init__(new_coeff, clean_zeros = False)
                divisible = True
                break
    return remainder

def _random_poly(_type, dim):
    '''
    Generates a random polynomial that has the form
    c_1x_1 + c_2x_2 + ... + c_nx_n where n = dim and each c_i is a randomly
    chosen integer between 0 and 1000.
    '''
    _vars = get_var_list(dim)

    random_poly_shape = [2 for i in range(dim)]

    random_poly_coeff = np.zeros(tuple(random_poly_shape), dtype=int)
    for var in _vars:
        random_poly_coeff[var] = np.random.randint(1000)

    if _type == 'MultiCheb':
        return MultiCheb(random_poly_coeff), _vars
    else:
        return MultiPower(random_poly_coeff), _vars

def _get_poly_with_LT(LT, GB):
    for poly in GB:
        if poly.lead_term == LT:
            return poly

def _test_zero_dimensional(_vars, GB):
    LT_list = [p.lead_term for p in GB]

    for var in _vars:
        exists_multiple = False
        for LT in LT_list:
            if np.linalg.matrix_rank(np.array([list(var), list(LT)])) == 1:
                exists_multiple = True
                break
        if not exists_multiple:
            return False

    return True

def _match_poly_dim(poly1, poly2):
    # Do nothing if they are already the same dimension
    if poly1.dim == poly2.dim:
        return poly1, poly2

    poly_type = ''
    if type(poly1) == MultiPower and type(poly2) == MultiPower:
        poly_type = 'MultiPower'
    elif type(poly1) == MultiCheb and type(poly2) == MultiCheb:
        poly_type = 'MultiCheb'
    else:
        raise ValueError('Polynomials must be the same type')

    poly1_vars = poly1.dim
    poly2_vars = poly2.dim
    max_vars = max(poly1_vars, poly2_vars)

    if poly1_vars < max_vars:
         for j in range(max_vars-poly1_vars):
             coeff_reshaped = poly1.coeff[...,np.newaxis]
         if poly_type == 'MultiPower':
             poly1 = MultiPower(coeff_reshaped)
         elif poly_type == 'MultiCheb':
             poly1 = MultiCheb(coeff_reshaped)
    elif poly2_vars < max_vars:
        for j in range(max_vars-poly2_vars):
            coeff_reshaped = poly2.coeff[...,np.newaxis]
        if poly_type == 'MultiPower':
            poly2 = MultiPower(coeff_reshaped)
        elif poly_type == 'MultiCheb':
            poly2 = MultiCheb(coeff_reshaped)

    return poly1, poly2

def newton_polish(polys,root,niter=100,tol=1e-5):
    """
    Perform Newton's method on a system of N polynomials in M variables.
    
    Parameters
    ----------
    polys : list
        A list of polynomial objects of the same type (MultiPower or MultiCheb).
    root : ndarray
        An initial guess for Newton's method, intended to be a candidate root from root_finder.
    niter : int 
        A maximum number of iterations of Newton's method.
    tol : float
        Tolerance for convergence of Newton's method.
        
    Returns
    -------
    x1 : ndarray
        The terminal point of Newton's method, an estimation for a root of the system
    """
    poly_type = ''
    if (all(type(p) == MultiCheb for p in polys)):
        poly_type = 'MultiCheb'
    elif (all(type(p) == MultiPower for p in polys)):
        poly_type = 'MultiPower'
    else:
        raise ValueError('All polynomials must be the same type')
        
    def f(x):
        m = len(polys)
        f_x = np.empty(m)
        for i, poly in enumerate(polys):
            f_x[i] = poly.evaluate_at(x)
        return f_x
        
    def Df(x):
        m = len(polys)
        dim = max(poly.dim for poly in polys)
        jac = np.empty((m,dim))
        for i, poly in enumerate(polys):
            jac[i] = poly.grad(x)
        return jac
        
    i = 0
    x0 = root
    while True:
        if i == niter:
            break
        delta = np.linalg.solve(Df(x0),-f(x0))
        x1 = delta + x0
        if np.linalg.norm(x1-x0) < tol:
            break
        x0 = x1
        i+=1
    return x1