from yroots.polynomial import getPoly
from yroots.polyroots import solve
import numpy as np

np.random.seed(2)
p1 = getPoly(2,2,True)
p2 = getPoly(24,2,True)
roots = solve([p1,p2],'qrt')[0]
res1 = np.abs(p1(roots))
res2 = np.abs(p2(roots))
print(res1.max(),res1.argmax())
print(res2.max(),res2.argmax())
print(roots[res1.argmax()])
print(roots[res2.argmax()])
