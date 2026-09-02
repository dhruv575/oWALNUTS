# posteriordb benchmark v2 — results

Seed medians over 3 seeds of the per-cell minimum over parameters; `gates` = cells passing R-hat <= 1.01, bulk/tail ESS >= 400, zero divergences; `div` = sampling divergences summed over chains per seed; `max|z|` = worst posterior-mean z against the posteriordb reference.

| model | arm | gates | wall s | grads | min bulk ESS | min tail ESS | bulk ESS/s | tail ESS/s | bulk ESS/grad x1e3 | max R-hat | div | max abs z |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| eight_schools-eight_schools_noncentered | owalnuts-da | 3/3 | 0.03 | 72,149 | 1,901 | 1,913 | 76,910.1 | 69,559.1 | 26.354 | 1.0026 | 0,0,0 | 1.66 |
| eight_schools-eight_schools_noncentered | owalnuts-paper | 3/3 | 0.03 | 70,943 | 1,845 | 1,654 | 74,741.6 | 67,025.5 | 26.246 | 1.0028 | 0,0,0 | 1.84 |
| eight_schools-eight_schools_noncentered | owalnuts-stan-style | 3/3 | 0.03 | 77,908 | 1,859 | 1,443 | 68,010.3 | 53,153.2 | 23.855 | 1.0027 | 0,0,0 | 1.42 |
| eight_schools-eight_schools_noncentered | cmdstan | 1/3 | 0.15 | 73,522 | 2,295 | 1,840 | 13,680.1 | 10,104.5 | 29.143 | 1.0030 | 0,1,1 | 1.81 |
| eight_schools-eight_schools_noncentered | nutpie | 0/3 | 0.13 | 55,781 | 1,912 | 1,708 | 14,030.0 | 11,841.2 | 34.548 | 1.0029 | 5,3,6 | 1.54 |
| eight_schools-eight_schools_centered | owalnuts-da | 0/3 | 0.07 | 177,982 | 108 | 88 | 1,284.4 | 1,088.1 | 0.563 | 1.0302 | 2,0,1 | 0.81 |
| eight_schools-eight_schools_centered | owalnuts-paper | 0/3 | 0.07 | 158,901 | 104 | 75 | 1,494.0 | 978.7 | 0.656 | 1.0379 | 1,1,2 | 1.73 |
| eight_schools-eight_schools_centered | owalnuts-stan-style | 0/3 | 0.07 | 169,163 | 82 | 66 | 760.0 | 873.9 | 0.483 | 1.0221 | 9,3,5 | 0.98 |
| eight_schools-eight_schools_centered | cmdstan | 0/3 | 0.19 | 171,387 | 174 | 184 | 341.4 | 469.2 | 1.017 | 1.0291 | 52,116,42 | 1.91 |
| eight_schools-eight_schools_centered | nutpie | 0/3 | 1.64 | 109,349 | 264 | 118 | 124.5 | 51.9 | 1.272 | 1.0197 | 73,23,20 | 3.21 |
| diamonds-diamonds | owalnuts-da | 3/3 | 72.83 | 4,782,706 | 868 | 1,194 | 11.6 | 15.1 | 0.183 | 1.0049 | 0,0,0 | 2.15 |
| diamonds-diamonds | owalnuts-paper | 3/3 | 56.31 | 4,199,839 | 792 | 1,065 | 14.3 | 20.2 | 0.194 | 1.0033 | 0,0,0 | 2.25 |
| diamonds-diamonds | owalnuts-stan-style | 3/3 | 52.29 | 4,206,088 | 712 | 869 | 13.9 | 16.0 | 0.178 | 1.0064 | 0,0,0 | 1.92 |
| diamonds-diamonds | cmdstan | 3/3 | 71.82 | 6,311,142 | 1,300 | 2,019 | 18.1 | 28.1 | 0.206 | 1.0045 | 0,0,0 | 2.01 |
| diamonds-diamonds | nutpie | 0/3 | 30.54 | 2,097,800 | 296 | 457 | 9.4 | 14.9 | 0.142 | 1.0203 | 0,0,0 | 2.14 |
| earnings-logearn_interaction | owalnuts-da | 2/3 | 49.20 | 3,880,805 | 706 | 730 | 14.2 | 14.7 | 0.175 | 1.0051 | 0,0,0 | 0.48 |
| earnings-logearn_interaction | owalnuts-paper | 2/3 | 39.98 | 3,635,661 | 742 | 777 | 15.5 | 16.3 | 0.192 | 1.0037 | 0,0,0 | 1.14 |
| earnings-logearn_interaction | owalnuts-stan-style | 0/3 | 3.79 | 419,997 | 145 | 263 | 38.2 | 69.4 | 0.345 | 1.0280 | 0,0,0 | 1.67 |
| earnings-logearn_interaction | cmdstan | 3/3 | 19.62 | 1,343,912 | 1,093 | 1,278 | 55.7 | 61.7 | 0.796 | 1.0047 | 0,0,0 | 0.75 |
| earnings-logearn_interaction | nutpie | 3/3 | 12.51 | 736,864 | 731 | 1,015 | 58.4 | 81.1 | 0.994 | 1.0057 | 0,0,0 | 0.87 |
| mesquite-logmesquite_logvash | owalnuts-da | 3/3 | 0.25 | 330,434 | 1,025 | 1,478 | 4,056.2 | 5,416.5 | 3.116 | 1.0039 | 0,0,0 | 1.53 |
| mesquite-logmesquite_logvash | owalnuts-paper | 3/3 | 0.26 | 322,041 | 991 | 1,420 | 3,784.1 | 5,198.0 | 3.017 | 1.0027 | 0,0,0 | 1.73 |
| mesquite-logmesquite_logvash | owalnuts-stan-style | 3/3 | 0.25 | 291,619 | 691 | 899 | 2,710.5 | 3,689.2 | 2.368 | 1.0068 | 0,0,0 | 0.98 |
| mesquite-logmesquite_logvash | cmdstan | 3/3 | 0.31 | 379,170 | 1,617 | 1,793 | 4,757.9 | 5,938.3 | 4.264 | 1.0036 | 0,0,0 | 2.02 |
| mesquite-logmesquite_logvash | nutpie | 3/3 | 0.56 | 194,494 | 879 | 1,208 | 1,571.9 | 2,202.3 | 4.501 | 1.0042 | 0,0,0 | 1.42 |
| kidiq-kidscore_momhsiq | owalnuts-da | 3/3 | 1.09 | 372,724 | 904 | 753 | 767.1 | 694.0 | 2.207 | 1.0056 | 0,0,0 | 1.65 |
| kidiq-kidscore_momhsiq | owalnuts-paper | 1/3 | 1.11 | 407,087 | 641 | 705 | 578.7 | 611.4 | 1.575 | 1.0114 | 0,0,0 | 1.39 |
| kidiq-kidscore_momhsiq | owalnuts-stan-style | 2/3 | 0.66 | 236,349 | 433 | 520 | 607.6 | 788.6 | 1.662 | 1.0077 | 0,0,0 | 0.91 |
| kidiq-kidscore_momhsiq | cmdstan | 3/3 | 0.95 | 363,370 | 1,682 | 1,786 | 1,788.0 | 1,854.5 | 4.507 | 1.0022 | 0,0,0 | 0.99 |
| kidiq-kidscore_momhsiq | nutpie | 2/3 | 0.57 | 138,988 | 754 | 1,116 | 1,314.2 | 1,934.6 | 5.425 | 1.0052 | 0,0,0 | 1.25 |
| sblrc-blr | owalnuts-da | 1/3 | 0.36 | 555,766 | 366 | 327 | 912.2 | 814.7 | 0.617 | 1.0092 | 0,0,0 | 1.12 |
| sblrc-blr | owalnuts-paper | 1/3 | 0.32 | 549,189 | 433 | 387 | 1,346.4 | 1,087.8 | 0.789 | 1.0054 | 0,0,0 | 1.24 |
| sblrc-blr | owalnuts-stan-style | 2/3 | 0.11 | 196,399 | 677 | 745 | 6,210.9 | 6,852.2 | 3.764 | 1.0070 | 0,0,0 | 0.56 |
| sblrc-blr | cmdstan | 3/3 | 0.16 | 126,890 | 887 | 1,149 | 5,066.9 | 6,723.5 | 6.993 | 1.0048 | 0,0,0 | 1.43 |
| sblrc-blr | nutpie | 3/3 | 0.13 | 55,870 | 884 | 1,370 | 6,664.4 | 11,254.3 | 15.869 | 1.0052 | 0,0,0 | 1.41 |
| nes2000-nes | owalnuts-da | 3/3 | 3.76 | 410,293 | 1,056 | 1,316 | 275.2 | 359.4 | 2.655 | 1.0032 | 0,0,0 | 2.07 |
| nes2000-nes | owalnuts-paper | 3/3 | 3.72 | 401,607 | 1,212 | 1,419 | 325.5 | 381.3 | 3.014 | 1.0043 | 0,0,0 | 1.66 |
| nes2000-nes | owalnuts-stan-style | 3/3 | 2.94 | 317,456 | 760 | 1,075 | 258.9 | 343.4 | 2.583 | 1.0048 | 0,0,0 | 1.51 |
| nes2000-nes | cmdstan | 3/3 | 3.48 | 396,502 | 1,920 | 2,156 | 552.4 | 613.3 | 4.869 | 1.0024 | 0,0,0 | 1.15 |
| nes2000-nes | nutpie | 3/3 | 2.69 | 237,884 | 1,313 | 1,767 | 487.2 | 651.4 | 5.519 | 1.0025 | 0,0,0 | 1.24 |
| arK-arK | owalnuts-da | 3/3 | 1.17 | 253,730 | 2,014 | 1,864 | 1,726.4 | 1,700.3 | 7.826 | 1.0031 | 0,0,0 | 1.50 |
| arK-arK | owalnuts-paper | 3/3 | 1.13 | 252,470 | 1,937 | 2,168 | 1,580.2 | 1,658.9 | 7.074 | 1.0024 | 0,0,0 | 1.99 |
| arK-arK | owalnuts-stan-style | 3/3 | 1.03 | 228,942 | 1,951 | 1,701 | 1,891.3 | 1,651.5 | 8.522 | 1.0031 | 0,0,0 | 2.05 |
| arK-arK | cmdstan | 3/3 | 1.23 | 244,526 | 2,619 | 2,287 | 2,041.3 | 1,737.1 | 10.557 | 1.0032 | 0,0,0 | 2.16 |
| arK-arK | nutpie | 3/3 | 7.40 | 174,917 | 1,956 | 1,966 | 271.2 | 279.9 | 11.181 | 1.0021 | 0,0,0 | 1.59 |
| arma-arma11 | owalnuts-da | 0/3 | 0.29 | 133,862 | 4 | 4 | 15.2 | 13.8 | 0.033 | 2.4684 | 1000,2000,4000 | 1.94 |
| arma-arma11 | owalnuts-paper | 0/3 | 0.22 | 116,353 | 4 | 4 | 19.9 | 18.1 | 0.038 | 2.4701 | 0,0,0 | 1.94 |
| arma-arma11 | owalnuts-stan-style | 0/3 | 0.30 | 162,034 | 4 | 4 | 13.4 | 13.4 | 0.025 | 2.4689 | 1000,2000,4000 | 1.94 |
| arma-arma11 | cmdstan | 2/3 | 0.21 | 49,087 | 3,614 | 2,717 | 17,940.5 | 13,487.3 | 73.630 | 1.0039 | 0,0,0 | 1.16 |
| arma-arma11 | nutpie | 2/3 | 1.77 | 36,716 | 4,677 | 2,679 | 3,046.4 | 1,515.3 | 146.686 | 1.0016 | 143,0,0 | 1.02 |
| garch-garch11 | owalnuts-da | 3/3 | 0.33 | 78,664 | 907 | 1,424 | 2,770.9 | 4,322.1 | 11.374 | 1.0059 | 0,0,0 | 1.20 |
| garch-garch11 | owalnuts-paper | 3/3 | 0.32 | 75,509 | 1,121 | 1,289 | 3,480.8 | 4,103.3 | 14.847 | 1.0029 | 0,0,0 | 2.35 |
| garch-garch11 | owalnuts-stan-style | 3/3 | 0.36 | 78,426 | 817 | 1,111 | 2,302.2 | 3,131.4 | 10.414 | 1.0048 | 0,0,0 | 1.20 |
| garch-garch11 | cmdstan | 3/3 | 0.53 | 89,418 | 1,937 | 1,832 | 3,767.1 | 3,348.8 | 21.607 | 1.0022 | 0,0,0 | 1.87 |
| garch-garch11 | nutpie | 3/3 | 2.26 | 61,813 | 1,593 | 1,955 | 611.8 | 872.0 | 25.918 | 1.0042 | 0,0,0 | 0.67 |
| gp_pois_regr-gp_pois_regr | owalnuts-da | 2/3 | 1.50 | 1,113,134 | 785 | 878 | 524.2 | 516.0 | 0.705 | 1.0022 | 0,0,0 | 1.95 |
| gp_pois_regr-gp_pois_regr | owalnuts-paper | 2/3 | 1.72 | 1,191,857 | 802 | 1,057 | 500.6 | 659.8 | 0.717 | 1.0046 | 0,0,0 | 2.25 |
| gp_pois_regr-gp_pois_regr | owalnuts-stan-style | 3/3 | 1.49 | 953,658 | 618 | 773 | 488.7 | 611.1 | 0.675 | 1.0071 | 0,0,0 | 1.86 |
| gp_pois_regr-gp_pois_regr | cmdstan | 0/3 | 1.48 | 1,246,117 | 1,133 | 1,728 | 773.5 | 1,048.2 | 0.931 | 1.0025 | 9,9,16 | 1.69 |
| gp_pois_regr-gp_pois_regr | nutpie | 0/3 | 4.74 | 771,999 | 823 | 846 | 118.9 | 122.3 | 1.066 | 1.0046 | 161,120,822 | 2.44 |
| hmm_example-hmm_example | owalnuts-da | 3/3 | 1.64 | 202,553 | 1,826 | 1,688 | 1,099.5 | 1,041.5 | 8.892 | 1.0028 | 0,0,0 | 1.42 |
| hmm_example-hmm_example | owalnuts-paper | 3/3 | 1.95 | 191,464 | 1,878 | 1,867 | 961.2 | 955.3 | 9.810 | 1.0037 | 0,0,0 | 2.20 |
| hmm_example-hmm_example | owalnuts-stan-style | 3/3 | 0.97 | 96,003 | 1,409 | 1,375 | 1,455.3 | 1,444.0 | 14.679 | 1.0039 | 0,0,0 | 1.43 |
| hmm_example-hmm_example | cmdstan | 3/3 | 1.27 | 98,735 | 2,266 | 1,828 | 1,665.9 | 1,334.7 | 23.701 | 1.0011 | 0,0,0 | 1.50 |
| hmm_example-hmm_example | nutpie | 3/3 | 9.37 | 56,404 | 1,800 | 1,885 | 192.1 | 211.3 | 31.961 | 1.0017 | 0,0,0 | 1.57 |
| bball_drive_event_0-hmm_drive_0 | owalnuts-da | 2/3 | 4.91 | 95,170 | 1,164 | 803 | 237.3 | 163.7 | 12.103 | 1.0067 | 0,0,0 | 1.20 |
| bball_drive_event_0-hmm_drive_0 | owalnuts-paper | 1/3 | 5.30 | 103,936 | 805 | 344 | 152.0 | 68.9 | 8.078 | 1.0076 | 0,0,0 | 2.10 |
| bball_drive_event_0-hmm_drive_0 | owalnuts-stan-style | 2/3 | 5.15 | 80,444 | 558 | 867 | 108.4 | 168.5 | 6.934 | 1.0080 | 0,0,0 | 1.45 |
| bball_drive_event_0-hmm_drive_0 | cmdstan | 2/3 | 8.18 | 80,057 | 2,913 | 1,044 | 247.9 | 88.8 | 33.516 | 1.0025 | 0,369,0 | 1.11 |
| bball_drive_event_0-hmm_drive_0 | nutpie | 2/3 | 15.01 | 40,910 | 3,851 | 1,620 | 265.7 | 115.2 | 94.134 | 1.0030 | 0,60,0 | 1.14 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts-da | 0/3 | 11.23 | 68,154 | 303 | 122 | 24.5 | 9.8 | 4.341 | 1.0159 | 0,0,0 | 1.00 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts-paper | 0/3 | 12.88 | 68,688 | 358 | 147 | 30.4 | 12.5 | 5.209 | 1.0136 | 0,0,0 | 1.57 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts-stan-style | 0/3 | 11.12 | 63,649 | 425 | 194 | 35.3 | 17.5 | 6.551 | 1.0073 | 0,0,0 | 1.84 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | cmdstan | 0/3 | 13.38 | 74,709 | 715 | 246 | 57.1 | 19.7 | 10.181 | 1.0080 | 13,9,9 | 1.68 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | nutpie | 0/3 | 28.64 | 50,976 | 569 | 247 | 20.7 | 9.0 | 11.408 | 1.0105 | 21,26,14 | 1.94 |
| hudson_lynx_hare-lotka_volterra | owalnuts-da | 1/3 | 26.00 | 280,419 | 7 | 11 | 0.2 | 0.4 | 0.025 | 1.5954 | 0,0,0 | 1.25 |
| hudson_lynx_hare-lotka_volterra | owalnuts-paper | 1/3 | 41.95 | 281,372 | 7 | 11 | 0.2 | 0.3 | 0.026 | 1.5915 | 0,0,0 | 1.93 |
| hudson_lynx_hare-lotka_volterra | owalnuts-stan-style | 2/3 | 8.55 | 248,620 | 763 | 1,086 | 89.2 | 127.1 | 3.067 | 1.0062 | 0,0,0 | 1.44 |
| hudson_lynx_hare-lotka_volterra | cmdstan | 3/3 | 5.67 | 275,143 | 1,001 | 1,381 | 176.5 | 241.1 | 3.642 | 1.0040 | 0,0,0 | 1.33 |
| hudson_lynx_hare-lotka_volterra | nutpie | 0/3 | 15.43 | 134,309 | 17 | 56 | 1.1 | 3.6 | 0.126 | 1.1709 | 347 | 1.58 |
| mcycle_gp-accel_gp | owalnuts-da | 0/3 | 5.74 | 1,373,518 | 67 | 71 | 13.5 | 12.3 | 0.056 | 1.0745 | 0,0,0 | 3.05 |
| mcycle_gp-accel_gp | owalnuts-paper | 0/3 | 7.61 | 1,718,430 | 52 | 48 | 6.8 | 5.5 | 0.030 | 1.0811 | 0,0,0 | 2.64 |
| mcycle_gp-accel_gp | owalnuts-stan-style | 0/3 | 5.03 | 1,023,264 | 16 | 11 | 4.7 | 3.4 | 0.018 | 1.2161 | 0,0,0 | 2.99 |
| mcycle_gp-accel_gp | cmdstan | 0/3 | 21.32 | 5,958,403 | 1,624 | 1,267 | 76.7 | 59.4 | 0.283 | 1.0042 | 14,63,102 | 2.42 |
| mcycle_gp-accel_gp | nutpie | 0/3 | 42.38 | 3,620,032 | 836 | 516 | 19.7 | 12.2 | 0.226 | 1.0076 | 159,113,127 | 2.23 |

## Appendix C versus dual averaging (paper / da, seed medians)

| model | r bulk ESS/grad | r tail ESS/grad | r bulk ESS/s | r gradients | da gates | paper gates | at least as good |
|---|---:|---:|---:|---:|---|---|---|
| eight_schools-eight_schools_noncentered | 0.996 | 0.910 | 0.972 | 0.983 | 3/3 | 3/3 | True |
| eight_schools-eight_schools_centered | 1.166 | 0.885 | 1.163 | 0.893 | 0/3 | 0/3 | True |
| diamonds-diamonds | 1.061 | 0.970 | 1.240 | 0.878 | 3/3 | 3/3 | True |
| earnings-logearn_interaction | 1.099 | 1.112 | 1.092 | 0.937 | 2/3 | 2/3 | True |
| mesquite-logmesquite_logvash | 0.968 | 0.993 | 0.933 | 0.975 | 3/3 | 3/3 | True |
| kidiq-kidscore_momhsiq | 0.714 | 0.822 | 0.754 | 1.092 | 3/3 | 1/3 | False |
| sblrc-blr | 1.278 | 1.188 | 1.476 | 0.988 | 1/3 | 1/3 | False |
| nes2000-nes | 1.135 | 1.068 | 1.183 | 0.979 | 3/3 | 3/3 | True |
| arK-arK | 0.904 | 1.035 | 0.915 | 0.995 | 3/3 | 3/3 | True |
| arma-arma11 | 1.151 | 1.150 | 1.310 | 0.869 | 0/3 | 0/3 | True |
| garch-garch11 | 1.305 | 0.926 | 1.256 | 0.960 | 3/3 | 3/3 | True |
| gp_pois_regr-gp_pois_regr | 1.018 | 1.225 | 0.955 | 1.071 | 2/3 | 2/3 | True |
| hmm_example-hmm_example | 1.103 | 1.145 | 0.874 | 0.945 | 3/3 | 3/3 | True |
| bball_drive_event_0-hmm_drive_0 | 0.667 | 0.397 | 0.641 | 1.092 | 2/3 | 1/3 | False |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 1.200 | 1.228 | 1.244 | 1.008 | 0/3 | 0/3 | True |
| hudson_lynx_hare-lotka_volterra | 1.024 | 1.011 | 0.920 | 1.003 | 1/3 | 1/3 | True |
| mcycle_gp-accel_gp | 0.538 | 0.506 | 0.503 | 1.251 | 0/3 | 0/3 | False |

Geometric mean over 17 models: bulk ESS/grad **0.995**, tail ESS/grad 0.940, bulk ESS/s 0.992, total gradients 0.991. Losing models: ['kidiq-kidscore_momhsiq', 'sblrc-blr', 'bball_drive_event_0-hmm_drive_0', 'mcycle_gp-accel_gp']. Preregistered decision rule -> recommend Appendix C as default: **False**.

## Head-to-head (geometric mean of seed-median ratios over models complete on both sides)

| comparison | models | bulk ESS/grad ratio | bulk ESS/s ratio | wall/grad ratio | wins ESS/s | wins ESS/grad | wins outright (gates >=, ESS/grad >, ESS/s >) |
|---|---:|---:|---:|---:|---:|---:|---|
| owalnuts-da_over_cmdstan | 17 | 0.233 | 0.307 | 0.771 | 2 | 0 | none |
| owalnuts-paper_over_cmdstan | 17 | 0.232 | 0.305 | 0.771 | 2 | 0 | none |
| owalnuts-stan-style_over_cmdstan | 17 | 0.319 | 0.450 | 0.767 | 3 | 0 | none |
| owalnuts-da_over_nutpie | 16 | 0.230 | 1.108 | 0.207 | 9 | 1 | diamonds-diamonds |
| owalnuts-paper_over_nutpie | 16 | 0.229 | 1.104 | 0.209 | 9 | 1 | diamonds-diamonds |
| owalnuts-stan-style_over_nutpie | 16 | 0.238 | 1.125 | 0.213 | 9 | 1 | diamonds-diamonds |

## v2 versus v1 (seed medians; ratio v2 / v1; v1 arms at their v1 settings: depth 8, h0 0.1, STAN_THREADS build)

| model | arm | v1 gates | v2 gates | v1 ESS/grad x1e3 | v2 ESS/grad x1e3 | ESS/grad v2/v1 | ESS/s v2/v1 | wall v2/v1 | grads v2/v1 |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| eight_schools-eight_schools_noncentered | owalnuts-da | 3/3 | 3/3 | 22.976 | 26.354 | 1.15 | 7.04 | 0.15 | 0.96 |
| eight_schools-eight_schools_noncentered | owalnuts-paper | 3/3 | 3/3 | 21.789 | 26.246 | 1.20 | 7.63 | 0.17 | 1.05 |
| eight_schools-eight_schools_noncentered | cmdstan | 1/3 | 1/3 | 32.473 | 29.143 | 0.90 | 0.96 | 0.93 | 0.99 |
| eight_schools-eight_schools_noncentered | nutpie | 0/3 | 0/3 | 40.495 | 34.548 | 0.85 | 1.00 | 0.83 | 1.00 |
| eight_schools-eight_schools_centered | owalnuts-da | 0/3 | 0/3 | 0.467 | 0.563 | 1.20 | 14.11 | 0.07 | 1.11 |
| eight_schools-eight_schools_centered | owalnuts-paper | 0/3 | 0/3 | 0.525 | 0.656 | 1.25 | 8.73 | 0.15 | 1.09 |
| eight_schools-eight_schools_centered | cmdstan | 0/3 | 0/3 | 0.641 | 1.017 | 1.59 | 0.61 | 0.86 | 1.02 |
| eight_schools-eight_schools_centered | nutpie | 0/3 | 0/3 | 1.599 | 1.272 | 0.80 | 0.81 | 1.52 | 0.98 |
| diamonds-diamonds | owalnuts-da | 0/3 | 3/3 | 0.022 | 0.183 | 8.18 | 8.73 | 2.74 | 3.04 |
| diamonds-diamonds | owalnuts-paper | 0/3 | 3/3 | 0.032 | 0.194 | 6.17 | 9.90 | 20.23 | 32.81 |
| diamonds-diamonds | cmdstan | 3/3 | 3/3 | 0.215 | 0.206 | 0.96 | 1.19 | 0.80 | 0.97 |
| diamonds-diamonds | nutpie | 1/3 | 0/3 | 0.163 | 0.142 | 0.87 | 0.81 | 0.89 | 1.00 |
| earnings-logearn_interaction | owalnuts-da | 0/3 | 2/3 | 0.015 | 0.175 | 12.00 | 12.79 | 2.59 | 2.57 |
| earnings-logearn_interaction | owalnuts-paper | 0/3 | 2/3 | 0.032 | 0.192 | 6.10 | 5.08 | 30.33 | 28.40 |
| earnings-logearn_interaction | cmdstan | 3/3 | 3/3 | 0.779 | 0.796 | 1.02 | 0.62 | 1.72 | 1.05 |
| earnings-logearn_interaction | nutpie | 2/3 | 3/3 | 0.884 | 0.994 | 1.12 | 0.75 | 1.55 | 1.00 |
| mesquite-logmesquite_logvash | owalnuts-da | 3/3 | 3/3 | 2.827 | 3.116 | 1.10 | 3.63 | 0.30 | 1.01 |
| mesquite-logmesquite_logvash | owalnuts-paper | 0/3 | 3/3 | 0.026 | 3.017 | 115.66 | 428.72 | 0.38 | 1.46 |
| mesquite-logmesquite_logvash | cmdstan | 3/3 | 3/3 | 3.841 | 4.264 | 1.11 | 1.00 | 1.02 | 1.04 |
| mesquite-logmesquite_logvash | nutpie | 3/3 | 3/3 | 4.255 | 4.501 | 1.06 | 0.78 | 1.32 | 0.99 |
| kidiq-kidscore_momhsiq | owalnuts-da | 3/3 | 3/3 | 2.668 | 2.207 | 0.83 | 1.16 | 0.82 | 1.13 |
| kidiq-kidscore_momhsiq | owalnuts-paper | 0/3 | 1/3 | 0.032 | 1.575 | 49.99 | 63.18 | 2.52 | 3.18 |
| kidiq-kidscore_momhsiq | cmdstan | 3/3 | 3/3 | 3.717 | 4.507 | 1.21 | 1.08 | 1.15 | 1.01 |
| kidiq-kidscore_momhsiq | nutpie | 3/3 | 2/3 | 5.019 | 5.425 | 1.08 | 1.17 | 0.92 | 1.00 |
| sblrc-blr | owalnuts-da | 0/3 | 1/3 | 0.295 | 0.617 | 2.09 | 6.64 | 0.37 | 1.25 |
| sblrc-blr | owalnuts-paper | 0/3 | 1/3 | 0.032 | 0.789 | 25.05 | 185.44 | 0.58 | 4.29 |
| sblrc-blr | cmdstan | 2/3 | 3/3 | 6.980 | 6.993 | 1.00 | 1.26 | 1.06 | 1.02 |
| sblrc-blr | nutpie | 3/3 | 3/3 | 15.500 | 15.869 | 1.02 | 0.99 | 1.11 | 0.98 |
| nes2000-nes | owalnuts-da | 3/3 | 3/3 | 2.401 | 2.655 | 1.11 | 1.43 | 0.70 | 0.99 |
| nes2000-nes | owalnuts-paper | 0/3 | 3/3 | 0.032 | 3.014 | 95.66 | 102.25 | 2.94 | 3.14 |
| nes2000-nes | cmdstan | 3/3 | 3/3 | 4.812 | 4.869 | 1.01 | 1.72 | 0.58 | 0.98 |
| nes2000-nes | nutpie | 3/3 | 3/3 | 5.470 | 5.519 | 1.01 | 1.36 | 0.72 | 1.01 |
| arK-arK | owalnuts-da | 3/3 | 3/3 | 7.770 | 7.826 | 1.01 | 10.06 | 0.11 | 1.05 |
| arK-arK | owalnuts-paper | 1/3 | 3/3 | 0.018 | 7.074 | 384.06 | 9652.88 | 0.04 | 0.81 |
| arK-arK | cmdstan | 3/3 | 3/3 | 10.607 | 10.557 | 1.00 | 0.87 | 1.19 | 1.02 |
| arK-arK | nutpie | 3/3 | 3/3 | 11.233 | 11.181 | 1.00 | 0.95 | 1.13 | 1.00 |
| arma-arma11 | owalnuts-da | 0/3 | 0/3 | — | 0.033 | — | — | — | — |
| arma-arma11 | owalnuts-paper | 0/3 | 0/3 | — | 0.038 | — | — | — | — |
| arma-arma11 | cmdstan | 2/3 | 2/3 | 44.984 | 73.630 | 1.64 | 3.46 | 0.30 | 0.72 |
| arma-arma11 | nutpie | 2/3 | 2/3 | 143.520 | 146.686 | 1.02 | 0.83 | 1.43 | 1.16 |
| garch-garch11 | owalnuts-da | 3/3 | 3/3 | 13.369 | 11.374 | 0.85 | 8.67 | 0.10 | 0.98 |
| garch-garch11 | owalnuts-paper | 3/3 | 3/3 | 11.973 | 14.847 | 1.24 | 12.85 | 0.10 | 1.01 |
| garch-garch11 | cmdstan | 3/3 | 3/3 | 20.259 | 21.607 | 1.07 | 1.30 | 0.83 | 1.01 |
| garch-garch11 | nutpie | 3/3 | 3/3 | 24.176 | 25.918 | 1.07 | 0.90 | 0.90 | 1.00 |
| gp_pois_regr-gp_pois_regr | owalnuts-da | 2/3 | 2/3 | 0.635 | 0.705 | 1.11 | 2.91 | 0.41 | 1.05 |
| gp_pois_regr-gp_pois_regr | owalnuts-paper | 0/3 | 2/3 | — | 0.717 | — | — | — | — |
| gp_pois_regr-gp_pois_regr | cmdstan | 0/3 | 0/3 | 1.088 | 0.931 | 0.86 | 0.99 | 0.86 | 0.94 |
| gp_pois_regr-gp_pois_regr | nutpie | 0/3 | 0/3 | 1.046 | 1.066 | 1.02 | 0.31 | 2.20 | 0.97 |
| hmm_example-hmm_example | owalnuts-da | 3/3 | 3/3 | 8.310 | 8.892 | 1.07 | 21.91 | 0.05 | 0.99 |
| hmm_example-hmm_example | owalnuts-paper | 0/3 | 3/3 | 0.015 | 9.810 | 640.09 | 17847.27 | 0.02 | 0.65 |
| hmm_example-hmm_example | cmdstan | 3/3 | 3/3 | 22.721 | 23.701 | 1.04 | 1.11 | 0.83 | 0.98 |
| hmm_example-hmm_example | nutpie | 3/3 | 3/3 | 26.604 | 31.961 | 1.20 | 1.04 | 1.16 | 0.99 |
| bball_drive_event_0-hmm_drive_0 | owalnuts-da | 2/3 | 2/3 | 7.500 | 12.103 | 1.61 | 11.61 | 0.15 | 1.02 |
| bball_drive_event_0-hmm_drive_0 | owalnuts-paper | 0/3 | 1/3 | 0.032 | 8.078 | 256.43 | 1720.97 | 0.12 | 0.81 |
| bball_drive_event_0-hmm_drive_0 | cmdstan | 3/3 | 2/3 | 59.655 | 33.516 | 0.56 | 0.25 | 1.79 | 1.07 |
| bball_drive_event_0-hmm_drive_0 | nutpie | 2/3 | 2/3 | 71.551 | 94.134 | 1.32 | 1.62 | 1.02 | 0.95 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts-da | 0/3 | 0/3 | 3.946 | 4.341 | 1.10 | 4.09 | 0.24 | 1.03 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts-paper | 1/3 | 0/3 | 2.241 | 5.209 | 2.32 | 20.86 | 0.04 | 0.32 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | cmdstan | 0/3 | 0/3 | 5.425 | 10.181 | 1.88 | 2.41 | 0.79 | 1.08 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | nutpie | 0/3 | 0/3 | 19.394 | 11.408 | 0.59 | 0.86 | 0.72 | 1.01 |
| hudson_lynx_hare-lotka_volterra | owalnuts-da | 1/3 | 1/3 | 3.529 | 0.025 | 0.01 | 0.00 | 2.80 | 1.03 |
| hudson_lynx_hare-lotka_volterra | owalnuts-paper | 0/3 | 1/3 | 0.026 | 0.026 | 0.99 | 0.69 | 2.42 | 1.81 |
| hudson_lynx_hare-lotka_volterra | cmdstan | 2/3 | 3/3 | 2.756 | 3.642 | 1.32 | 1.67 | 0.72 | 1.03 |
| hudson_lynx_hare-lotka_volterra | nutpie | 1/3 | 0/3 | 1.364 | 0.126 | 0.09 | 0.03 | 2.88 | 0.98 |
| mcycle_gp-accel_gp | owalnuts-da | 0/3 | 0/3 | 0.009 | 0.056 | 6.11 | 9.79 | 1.19 | 1.77 |
| mcycle_gp-accel_gp | owalnuts-paper | 0/3 | 0/3 | 0.032 | 0.030 | 0.96 | 1.43 | 8.97 | 13.43 |
| mcycle_gp-accel_gp | cmdstan | 0/3 | 0/3 | 0.230 | 0.283 | 1.23 | 1.36 | 0.86 | 1.05 |
| mcycle_gp-accel_gp | nutpie | 0/3 | 0/3 | 0.191 | 0.226 | 1.18 | 0.49 | 2.48 | 1.00 |

| arm | v1 cells passed | v2 cells passed | geomean ESS/grad v2/v1 | geomean ESS/s v2/v1 |
|---|---:|---:|---:|---:|
| owalnuts-da | 26 | 32 | 1.22 | 3.81 |
| owalnuts-paper | 8 | 29 | 13.87 | 55.19 |
| cmdstan | 34 | 35 | 1.10 | 1.11 |
| nutpie | 29 | 27 | 0.87 | 0.71 |

## Preregistered predictions

| prediction | value | held |
|---|---|---|
| P1_da_gate_passes_ge_33_of_51 | 32 | False |
| P2_da_geomean_bulk_ess_per_gradient_vs_cmdstan_ge_0.45 | 0.233 | False |
| P3_da_wall_per_gradient_within_1.5x_cmdstan | 0.771 | True |
| P4_paper_arm_no_frozen_cells | ['arma-arma11/78101', 'arma-arma11/78102', 'arma-arma11/78103', 'hudson_lynx_hare-lotka_volterra/78102', 'hudson_lynx_hare-lotka_volterra/78103'] | False |
| P5_zero_owalnuts_cells_lost_to_fatal_nan_or_start_failure | [] | True |
