# Plan cell check (1200 positions of 1530 tried; the coach plays up to 1,200 moves, by the tile needed)

## By plan step
| step | n | plan | other | broken | none | plan: grown in place | median moves to plan |
|---|---|---|---|---|---|---|---|
| blocked | 196 | 8% | 57% | 34% | 1% | 94% | 30 |
| build | 91 | 37% | 14% | 43% | 5% | 68% | 14 |
| grow | 796 | 45% | 21% | 29% | 5% | 86% | 35 |
| merge | 117 | 92% | 2% | 6% | 0% | 4% | 1 |

## By stage (biggest tile)
| stage | n | plan | other | broken | none | plan: grown in place | median moves to plan |
|---|---|---|---|---|---|---|---|
| 2048+ | 731 | 44% | 25% | 25% | 6% | 68% | 23 |
| 512-1024 | 355 | 46% | 27% | 26% | 1% | 74% | 16 |
| 64-256 | 114 | 25% | 11% | 64% | 0% | 28% | 3 |

## By the tile the plan cell needs
| need | n | plan | other | broken | none | plan: grown in place | median moves to plan |
|---|---|---|---|---|---|---|---|
| 1024 | 65 | 49% | 17% | 34% | 0% | 97% | 441 |
| 128 | 84 | 37% | 21% | 29% | 13% | 77% | 54 |
| 16 | 230 | 40% | 27% | 31% | 2% | 59% | 10 |
| 2048 | 44 | 27% | 14% | 59% | 0% | 100% | 846 |
| 256 | 100 | 53% | 31% | 16% | 0% | 89% | 110 |
| 32 | 162 | 41% | 23% | 30% | 6% | 59% | 11 |
| 4096 | 21 | 0% | 0% | 0% | 100% | 0% | - |
| 512 | 88 | 59% | 17% | 24% | 0% | 94% | 192 |
| 64 | 78 | 40% | 29% | 26% | 5% | 74% | 31 |
| 8 | 328 | 44% | 27% | 30% | 0% | 47% | 5 |

## Positions where the plan cell is what turns green today
| green_is_plan | n | plan | other | broken | none | plan: grown in place | median moves to plan |
|---|---|---|---|---|---|---|---|
| False | 473 | 47% | 24% | 26% | 3% | 50% | 6 |
| True | 727 | 40% | 24% | 31% | 5% | 81% | 26 |
