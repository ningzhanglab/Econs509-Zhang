## Stage-2 validation solvers (N=100, uniform [0,20])

| Method | Passes | Updates | Inner steps | Seconds | Exit metric | Status |
| --- | --- | --- | --- | --- | --- | --- |
| vfi | 379 | 378 | 0 | 0.013540 | 9.72104602706e-09 | converged |
| howard | 18 | 17 | 0 | 0.005993 | 1.84862340447e-16 | converged |
| modified_howard | 19 | 18 | 360 | 0.002994 | 9.37659630034e-09 | converged |

## Stage-3 invariant distributions

| Method | Seconds | Raw minimum | Correction mass | Stationarity |
| --- | --- | --- | --- | --- |
| dense_power | 0.001680 | 0 | -0 | 7.99776911364e-13 |
| dense_eigen | 0.015622 | -7.25973096612e-27 | 8.57555720372e-26 | 2.77555756156e-17 |
| dense_direct | 0.003534 | 0 | -0 | 2.77555756156e-17 |
| sparse_power | 0.003229 | 0 | -0 | 7.99776911364e-13 |
| sparse_eigen | 0.003085 | -1.45194619322e-26 | 5.28372294378e-25 | 2.77555756156e-17 |
| sparse_direct | 0.001050 | 0 | -0 | 0 |
