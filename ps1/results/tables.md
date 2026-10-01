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

## Part (a): baseline solvers, N=1000 uniform [0,20]

| Method | Passes | Updates | Inner steps | Seconds | Exit metric | Status |
| --- | --- | --- | --- | --- | --- | --- |
| vfi | 379 | 378 | 0 | 0.923665 | 9.71806129077e-09 | converged |
| howard | 15 | 14 | 0 | 0.063859 | 6.01925131926e-16 | converged |
| modified_howard | 19 | 18 | 360 | 0.055136 | 9.33987779834e-09 | converged |
| gradient | 20000 | 20000 | 0 | 51.552503 | 1.25760126001 | capped_unconverged |
| adam | 20000 | 20000 | 0 | 51.727502 | 0.125113107262 | capped_unconverged |

## Parts (b)–(c): common Howard policy

| Method | Seconds | Power updates | Raw minimum | Correction mass | Stationarity |
| --- | --- | --- | --- | --- | --- |
| dense_power | 0.238683 | 212 | 0 | -0 | 7.76899378163e-13 |
| dense_eigen | 0.074303 | n/a | -8.06313061579e-28 | 4.45487966523e-26 | 1.73472347598e-17 |
| dense_direct | 0.036680 | n/a | 0 | -0 | 3.1918911958e-16 |
| sparse_power | 0.003668 | 212 | 0 | -0 | 7.76906317057e-13 |
| sparse_eigen | 0.005532 | n/a | -4.0315653079e-28 | 2.01578265395e-26 | 1.38777878078e-17 |
| sparse_direct | 0.005262 | n/a | 0 | -0 | 8.48773347979e-18 |

## Parts (b)–(c): distribution differences

| Comparison | Maximum difference | Pair |
| --- | --- | --- |
| dense | 5.49010836792e-12 | dense_power, dense_direct |
| sparse | 5.48994877336e-12 | sparse_power, sparse_eigen |
| across_representations | 5.49011530682e-12 | dense_direct, sparse_power |
| all_six | 5.49011530682e-12 | dense_direct, sparse_power |

## Part (a): numerical theory diagnostics

| Quantity | Value |
| --- | --- |
| Contraction expression | 451.24401589 |
| Observed VFI outer passes | 379 |
| Specified 1/(1-beta)^2 expression | 625 |
| zero_values: sigma_min | 0.00131755850852 |
| zero_values: sigma_max | 30.3591830961 |
| zero_values: condition_J | 23041.9999566 |
| zero_values: condition_JtJ | 530933762 |
| howard_solution: sigma_min | 0.0199827991366 |
| howard_solution: sigma_max | 2.03095066516 |
| howard_solution: condition_J | 101.634943697 |
| howard_solution: condition_JtJ | 10329.6617804 |

## Part (e): uniform range trials, N=1000; selected methods

| k_max | Top mass | Support endpoint | Support share | Compute seconds | Range status |
| --- | --- | --- | --- | --- | --- |
| 1 | 0.0237509414545 | 1 | 1.000000 | 0.085518 | rejected_truncated |
| 2 | 6.01277209443e-05 | 2 | 1.000000 | 0.082441 | rejected_truncated |
| 5 | 0 | 3.21821821822 | 0.634000 | 0.074443 | eligible |
| 10 | 0 | 3.21321321321 | 0.322000 | 0.072260 | eligible |
| 20 | 0 | 3.26326326326 | 0.164000 | 0.072538 | eligible |
| 40 | 0 | 3.24324324324 | 0.082000 | 0.074047 | eligible |

## Part (f): uniform and exp-log, N=1000 at selected range

| Quantity | Uniform | Exp-log |
| --- | --- | --- |
| Outer passes | 19 | 19 |
| Updates | 18 | 18 |
| Inner steps | 360 | 360 |
| Exit metric | 8.07103857078e-09 | 8.0834666578e-09 |
| Solver seconds | 0.0566389579981 | 0.0530802919966 |
| Power updates | 172 | 168 |
| Distribution seconds | 0.00352920899604 | 0.00297812499775 |
| Compute seconds | 0.0831304579915 | 0.0757789579875 |
| Maximum grid step | 0.00500500500501 | 0.0107516734031 |
| Mean assets | 0.450551165217 | 0.450853905799 |
| Top mass | 0 | 0 |
| Support endpoint | 3.21821821822 | 3.21407251709 |
| Support share | 0.634 | 0.799 |
| Slack count | 1978 | 1945 |
| Slack mass | 0.90977107721 | 0.911966346902 |
| Upper choices | 0 | 0 |
| Euler maximum | 0.00412096375367 | 0.00612421604424 |
| Euler mean | 0.00120403136135 | 0.00108912237111 |
| Conditional weighted mean | 0.00147199905766 | 0.0008046570183 |
| Weighted maximum: max(qE) | 0.000102998957978 | 6.13602452215e-05 |
| Supported slack maximum | 0.00412096375367 | 0.00407219098769 |

## Part (g): selected methods, range, and grid across five node counts

| Quantity | N=100 | N=500 | N=1000 | N=2000 | N=5000 |
| --- | --- | --- | --- | --- | --- |
| Outer passes | 19 | 19 | 19 | 19 | 19 |
| Updates | 18 | 18 | 18 | 18 | 18 |
| Inner steps | 360 | 360 | 360 | 360 | 360 |
| Exit metric | 8.03364122753e-09 | 8.07799018063e-09 | 8.0834666578e-09 | 8.07986477462e-09 | 8.08314692909e-09 |
| Utility seconds | 0.000309292001475 | 0.00679545800085 | 0.0241041250047 | 0.112672458003 | 0.655352125003 |
| Solver seconds | 0.00388824900438 | 0.0156604590011 | 0.0537732079974 | 0.212434167006 | 1.285760583 |
| CSR construction seconds | 0.000102291996882 | 0.000170540995896 | 0.000141750002513 | 0.000179458002094 | 0.000298332997772 |
| Power seconds | 0.00271195799724 | 0.00287229099922 | 0.00301779100118 | 0.00373687600222 | 0.00624258299649 |
| Power updates | 168 | 169 | 168 | 168 | 168 |
| Compute seconds | 0.00701179099997 | 0.0254987489971 | 0.0810368740058 | 0.329022959013 | 1.947653624 |
| Stationarity residual | 7.87911402789e-13 | 7.53008766452e-13 | 8.48758563432e-13 | 8.50611248104e-13 | 8.52012904673e-13 |
| Maximum grid step | 0.107614708755 | 0.0215055689019 | 0.0107516734031 | 0.00537555790023 | 0.00215015611502 |
| Mean assets | 0.439732993184 | 0.45019078318 | 0.450853905799 | 0.450965370158 | 0.451126535212 |
| Top mass | 2.67276471009e-53 | 0 | 0 | 0 | 0 |
| Support endpoint | 3.02929208117 | 3.22015069022 | 3.21407251709 | 3.2072684858 | 3.17018140386 |
| Support share | 0.78 | 0.802 | 0.799 | 0.793 | 0.7888 |
| Slack count | 193 | 972 | 1945 | 3891 | 9730 |
| Slack mass | 0.896989880687 | 0.911024525526 | 0.911966346902 | 0.912035439329 | 0.912256038332 |
| Upper choices | 1 | 0 | 0 | 0 | 0 |
| Euler maximum | 0.0469940723466 | 0.0102519768383 | 0.00612421604424 | 0.00293533782662 | 0.00118455627353 |
| Euler mean | 0.0117693950252 | 0.00225801889311 | 0.00108912237111 | 0.000563182483879 | 0.000223018069011 |
| Conditional weighted mean | 0.0087004085652 | 0.00150289123749 | 0.0008046570183 | 0.000395872498082 | 0.000155907135197 |
| Weighted maximum: max(qE) | 0.000767549255638 | 0.000121869663975 | 6.13602452215e-05 | 1.72349708195e-05 | 6.44444556925e-06 |
| Supported slack maximum | 0.0469940723466 | 0.00780556323862 | 0.00407219098769 | 0.00197919372155 | 0.000966044811544 |

## Part (h): selected-grid Euler diagnostics; weighted maximum is max(qE)

| Quantity | Value |
| --- | --- |
| slack_count | 9730 |
| slack_mass | 0.912256038332 |
| upper_choice_count | 0 |
| maximum | 0.00118455627353 |
| mean | 0.000223018069011 |
| weighted_mean | 0.000155907135197 |
| weighted_maximum | 6.44444556925e-06 |
| supported_maximum | 0.000966044811544 |

## Part (h): OLS log(error) against log(maximum grid step)

| Error summary | Intercept | Slope | Used grids | Reason |
| --- | --- | --- | --- | --- |
| mean | -2.19734219457 | 1.01328727392 | 5 | available |
| maximum | -0.957782213685 | 0.933748380727 | 5 | available |
