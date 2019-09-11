import numpy as np
import itertools
from scipy.linalg import qr, solve_triangular, qr_multiply
from yroots.polynomial import Polynomial, MultiCheb, MultiPower
from yroots.utils import row_swap_matrix, MacaulayError, slice_top, mon_combos, \
                              num_mons_full, memoized_all_permutations, mons_ordered, \
                              all_permutations_cheb, ConditioningError
from matplotlib import pyplot as plt
from scipy.linalg import svd

def add_polys(degree, poly, poly_coeff_list):
    """Adds polynomials to a Macaulay Matrix.

    This function is called on one polynomial and adds all monomial multiples of
     it to the matrix.

    Parameters
    ----------
    degree : int
        The degree of the Macaulay Matrix
    poly : Polynomial
        One of the polynomials used to make the matrix.
    poly_coeff_list : list
        A list of all the current polynomials in the matrix.
    Returns
    -------
    poly_coeff_list : list
        The original list of polynomials in the matrix with the new monomial
        multiplications of poly added.
    """

    poly_coeff_list.append(poly.coeff)
    deg = degree - poly.degree
    dim = poly.dim

    mons = mon_combos([0]*dim,deg)

    for mon in mons[1:]: #skips the first all 0 mon
        poly_coeff_list.append(poly.mon_mult(mon, returnType = 'Matrix'))
    return poly_coeff_list

def find_degree(poly_list, verbose=False):
    '''Finds the appropriate degree for the Macaulay Matrix.

    Parameters
    --------
    poly_list: list
        The polynomials used to construct the matrix.
    verbose : bool
        If True prints the degree
    Returns
    -----------
    find_degree : int
        The degree of the Macaulay Matrix.

    '''
    if verbose:
        print('Degree of Macaulay Matrix:', sum(poly.degree for poly in poly_list) - len(poly_list) + 1)
    return sum(poly.degree for poly in poly_list) - len(poly_list) + 1

def rrqr_reduceMacaulay(matrix, matrix_terms, cuts, accuracy = 1.e-10, return_perm=False):
    ''' Reduces a Macaulay matrix, BYU style.

    The matrix is split into the shape
    A B C
    D E F
    Where A is square and contains all the highest terms, and C contains all the x,y,z etc. terms. The lengths
    are determined by the matrix_shape_stuff tuple. First A and D are reduced using rrqr without pivoting, and then the rest of
    the matrix is multiplied by Q.T to change it accordingly. Then E is reduced by rrqr with pivoting, the rows of B are shifted
    accordingly, and F is multipled by Q.T to change it accordingly. This is all done in place to save memory.

    Parameters
    ----------
    matrix : numpy array.
        The Macaulay matrix, sorted in BYU style.
    matrix_terms: numpy array
        Each row of the array contains a term in the matrix. The i'th row corresponds to
        the i'th column in the matrix.
    cuts : tuple
        When the matrix is reduced it is split into 3 parts with restricted pivoting. These numbers indicate
        where those cuts happen.
    accuracy : float
        Throws an error if the condition number of the backsolve is more than 1/accuracy.
    Returns
    -------
    matrix : numpy array
        The reduced matrix.
    matrix_terms: numpy array
        The resorted matrix_terms.
    Raises
    ------
    ConditioningError if the conditioning number of the Macaulay matrix after
    QR is greater than 1/accuracy.
    '''
    #controller variables for each part of the matrix
    AD = matrix[:,:cuts[0]]
    
    BCEF = matrix[:,cuts[0]:]
    # A = matrix[:cuts[0],:cuts[0]]
    B = matrix[:cuts[0],cuts[0]:cuts[1]]
    # C = matrix[:cuts[0],cuts[1]:]
    # D = matrix[cuts[0]:,:cuts[0]]
    E = matrix[cuts[0]:,cuts[0]:cuts[1]]
    F = matrix[cuts[0]:,cuts[1]:]

    #RRQR reduces A and D without pivoting sticking the result in it's place.
    Q1,matrix[:,:cuts[0]] = qr(AD)

    #Multiplying BCEF by Q.T
    BCEF[...] = Q1.T @ BCEF
    del Q1 #Get rid of Q1 for memory purposes.

    #RRQR reduces E sticking the result in it's place.
    Q,E[...],P = qr(E, pivoting = True)

    #Multiplies F by Q.T.
    F[...] = Q.T @ F
    del Q #Get rid of Q for memory purposes.

    #Permute the columns of B
    B[...] = B[:,P]

    #Resorts the matrix_terms.
    matrix_terms[cuts[0]:cuts[1]] = matrix_terms[cuts[0]:cuts[1]][P]

    #eliminate zero rows from the bottom of the matrix.
    matrix = row_swap_matrix(matrix)
    for row in matrix[::-1]:
        if np.allclose(row, 0,atol=accuracy):
            matrix = matrix[:-1]
        else:
            break

<<<<<<< HEAD
    #SVD conditioning check
    S = np.linalg.svd(matrix[:,:matrix.shape[0]], compute_uv=False)
    if S[0] * accuracy > S[-1]:
        return -1, -1
=======
    #Conditioning check
    cond_num = np.linalg.cond(matrix[:,:matrix.shape[0]])
    if cond_num*accuracy > 1:
        raise ConditioningError("Conditioning number of the Macaulay matrix "\
                                + "after QR is: " + str(cond_num))

>>>>>>> f4050f806e782d88870e1000cf3b50dd02bd3ba0
    #backsolve
    height = matrix.shape[0]
    matrix[:,height:] = solve_triangular(matrix[:,:height],matrix[:,height:])
    matrix[:,:height] = np.eye(height)
    
    if return_perm:
        perm = np.arange(matrix.shape[1])
        perm[cuts[0]:cuts[1]] = perm[cuts[0]:cuts[1]][P]
        return matrix, matrix_terms, perm
        
    return matrix, matrix_terms

def rrqr_reduceMacaulay2(matrix, matrix_terms, cuts, accuracy = 1.e-10):
    ''' Reduces a Macaulay matrix, BYU style

    This function does the same thing as rrqr_reduceMacaulay but uses
    qr_multiply instead of qr and a multiplication
    to make the function faster and more memory efficient.

    Parameters
    ----------
    matrix : numpy array.
        The Macaulay matrix, sorted in BYU style.
    matrix_terms: numpy array
        Each row of the array contains a term in the matrix. The i'th row corresponds to
        the i'th column in the matrix.
    cuts : tuple
        When the matrix is reduced it is split into 3 parts with restricted pivoting. These numbers indicate
        where those cuts happen.
    accuracy : float
        What is determined to be 0.
    Returns
    -------
    matrix : numpy array
        The reduced matrix.
    matrix_terms: numpy array
        The resorted matrix_terms.
    Raises
    ------
    ConditioningError if the conditioning number of the Macaulay matrix after
    QR is greater than 1/accuracy.
    '''
    #controller variables for each part of the matrix
    AD = matrix[:,:cuts[0]]
    BCEF = matrix[:,cuts[0]:]
    BC = matrix[:cuts[0],cuts[0]:]
    A = matrix[:cuts[0],:cuts[0]]
    B = matrix[:cuts[0],cuts[0]:cuts[1]]
    # C = matrix[:cuts[0],cuts[1]:]
    D = matrix[cuts[0]:,:cuts[0]]
    EF = matrix[cuts[0]:,cuts[0]:]
    E = matrix[cuts[0]:,cuts[0]:cuts[1]]
    F = matrix[cuts[0]:,cuts[1]:]

    #RRQR reduces A and multiplies BC.T by Q
    product1, A[...] = qr_multiply(AD, BCEF.T, mode = 'right')
    #BC is now Q.T @ BC
    BC[...] = product1.T
    del product1 #remove for memory purposes

    #set small values to zero before backsolving
    matrix[np.isclose(matrix, 0, atol=accuracy)] = 0
    #backsolve top of matrix (solve triangular on B and C)
    BC[...] = solve_triangular(A,BC)
    A[...] = np.eye(cuts[0]) #A is now the identity after backsolving
    #Adjust E and F: subtract off D times BC
    EF[...] -= D @ BC

    #QRP on E, multiply that onto F
    product2,R,P = qr_multiply(E, F.T, mode = 'right', pivoting = True)
    #get rid of zero rows, which may resize DEF
    matrix = matrix[:R.shape[0]+cuts[0]]
    D = matrix[cuts[0]:,:cuts[0]]
    EF = matrix[cuts[0]:,cuts[0]:]
    #set D to zero
    D[...] = np.zeros_like(D)
    #fill EF in with R and product2.T
    EF[:,:R.shape[1]] = R
    EF[:,R.shape[1]:] = product2.T
    del product2,R

    #Permute the columns of B, since E already got permuted implicitly
    B[...] = B[:,P]
    matrix_terms[cuts[0]:cuts[1]] = matrix_terms[cuts[0]:cuts[1]][P]
    del P

    #eliminate zero rows from the bottom of the matrix.
    matrix = row_swap_matrix(matrix)
    for row in matrix[::-1]:
        if np.allclose(row, 0,atol=accuracy):
            matrix = matrix[:-1]
        else:
            break

<<<<<<< HEAD
    #SVD conditioning check
    S = np.linalg.svd(matrix[:,:matrix.shape[0]], compute_uv=False)
    if S[0] * accuracy > S[-1]:
        return -1, -1
=======
    #Conditioning check
    cond_num = np.linalg.cond(matrix[:,:matrix.shape[0]])
    if cond_num*accuracy > 1:
        raise ConditioningError("Conditioning number of the Macaulay matrix "\
                                + "after QR is: " + str(cond_num))
>>>>>>> f4050f806e782d88870e1000cf3b50dd02bd3ba0

    #backsolve
    height = matrix.shape[0]
    matrix[:,height:] = solve_triangular(matrix[:,:height],matrix[:,height:])
    matrix[:,:height] = np.eye(height)

    return matrix, matrix_terms