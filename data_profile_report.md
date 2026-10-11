# Phase 0 Data Profile Report

```
==============================================================================
PHASE 0 DATA PROFILE  -  Returnformer / Returns Risk Engine
data_dir: data/clean
==============================================================================

==============================================================================
1. FILE LOADING
==============================================================================
  [OK]       event_train      -> event_table_training.p  (1,343,912 rows x 3 cols, 32.3 MB)
  [OK]       event_test       -> event_table_testing.p  (1,432,449 rows x 3 cols, 34.4 MB)
  [OK]       customer_train   -> customer_nodes_training.p  (764,725 rows x 31 cols, 185.1 MB)
  [OK]       customer_test    -> customer_nodes_testing.p  (812,220 rows x 31 cols, 196.6 MB)
  [OK]       product_train    -> product_nodes_training.p  (411,495 rows x 42 cols, 141.6 MB)
  [OK]       product_test     -> product_nodes_testing.p  (411,544 rows x 42 cols, 141.6 MB)

==============================================================================
2. SCHEMA DETECTION
==============================================================================
  label                 : isReturned                     [OK]
  customer_key          : hash(customerId)               [OK]
  product_key           : hash(variantID)                [OK]
  event_customer_key    : hash(customerId)               [OK]
  event_product_key     : hash(variantID)                [OK]

==============================================================================
3. TABLE PROFILE - event_train
==============================================================================
  shape: 1,343,912 rows x 3 cols
  memory: 32.3 MB in RAM
  expected column count (PRD): 3  |  actual: 3

  dtypes:
    int64       : 3 cols

  missing values:
    none

  numeric summary (non-family columns, up to 12):
                              mean           std           min           50%           max
    hash(variantID)   1.794308e+15  5.324234e+18 -9.223305e+18  1.199522e+15  9.223356e+18
    hash(customerId)  4.147685e+04  1.239380e+09 -2.147478e+09  2.939676e+06  2.147476e+09
    isReturned        5.540000e-01  4.970000e-01  0.000000e+00  1.000000e+00  1.000000e+00

  low-cardinality columns (<=10 uniques):
    isReturned                       (2 uniq): 1:744,867, 0:599,045

==============================================================================
3. TABLE PROFILE - customer_train
==============================================================================
  shape: 764,725 rows x 31 cols
  memory: 227.9 MB in RAM
  expected column count (PRD): 30  |  actual: 31

  dtypes:
    int64       : 16 cols
    float64     : 14 cols
    object      : 1 cols

  wide column families (>=3 cols sharing a stem):
    customerId_level_return_code_*          : 13 columns
    Country_*                               : 9 columns

  missing values:
    none

  numeric summary (non-family columns, up to 12):
                                           mean           std           min       50%           max
    hash(customerId)               -1047530.562  1.239333e+09 -2.147478e+09 -465296.0  2.147476e+09
    yearOfBirth                        1991.274  8.988000e+00  1.931000e+03    1993.0  2.022000e+03
    isMale                                0.186  3.890000e-01  0.000000e+00       0.0  1.000000e+00
    premier                               0.073  2.610000e-01  0.000000e+00       0.0  1.000000e+00
    salesPerCustomer                     11.553  1.114100e+01  1.000000e+00       9.0  3.015000e+03
    returnsPerCustomer                    6.088  7.061000e+00  1.000000e+00       4.0  3.690000e+02
    customerReturnRate                    0.541  2.710000e-01  1.000000e-03       0.5  1.000000e+00
    customerId_level_return_code_A        0.048  1.540000e-01  0.000000e+00       0.0  1.000000e+00
    customerId_level_return_code_B        0.033  1.300000e-01  0.000000e+00       0.0  1.000000e+00
    customerId_level_return_code_C        0.007  6.800000e-02  0.000000e+00       0.0  1.000000e+00
    customerId_level_return_code_D        0.030  1.150000e-01  0.000000e+00       0.0  1.000000e+00
    customerId_level_return_code_E        0.000  2.000000e-03  0.000000e+00       0.0  1.000000e+00

  low-cardinality columns (<=10 uniques):
    isMale                           (2 uniq): 0:622,757, 1:141,968
    shippingCountry                  (9 uniq): Country_G:410,237, Country_E:178,318, Country_H:63,210, Country_D:37,174, Country_I:25,281, Country_F:15,900
    premier                          (2 uniq): 0:708,551, 1:56,174
    customerId_level_return_code_E   (9 uniq): 0.0:764,716, 1.0:2, 0.25:1, 0.0681818181818181:1, 0.5384615384615384:1, 0.2:1
    Country_A                        (2 uniq): 0:749,613, 1:15,112
    Country_B                        (2 uniq): 0:754,349, 1:10,376
    Country_C                        (2 uniq): 0:755,608, 1:9,117
    Country_D                        (2 uniq): 0:727,551, 1:37,174

==============================================================================
3. TABLE PROFILE - product_train
==============================================================================
  shape: 411,495 rows x 42 cols
  memory: 141.6 MB in RAM
  expected column count (PRD): 44  |  actual: 42

  dtypes:
    int64       : 26 cols
    float64     : 16 cols

  wide column families (>=3 cols sharing a stem):
    variantID_level_return_code_*           : 13 columns
    productType_*                           : 11 columns
    Brand_*                                 : 10 columns

  missing values:
    none

  numeric summary (non-family columns, up to 12):
                                           mean           std           min           50%           max
    hash(variantID)               -9.448308e+15  5.321631e+18 -9.223305e+18 -1.289546e+16  9.223333e+18
    hash(productID)               -6.073247e+14  5.343471e+18 -9.223352e+18 -5.108932e+15  9.223271e+18
    hash(supplierRef)             -7.067751e+06  1.241336e+09 -2.147436e+09 -2.041634e+07  2.147480e+09
    avgGbpPrice                    2.758400e+01  2.349300e+01  1.250000e+00  2.146000e+01  5.180000e+02
    avgDiscountValue               1.757500e+01  2.376000e+00  0.000000e+00  1.774000e+01  4.533000e+01
    salesPerProduct                4.280400e+01  7.598900e+01  1.000000e+00  2.200000e+01  9.426000e+03
    returnsPerProduct              1.325300e+01  2.021100e+01  1.000000e+00  7.000000e+00  1.074000e+03
    productReturnRate              3.850000e-01  2.110000e-01  1.000000e-03  3.600000e-01  1.000000e+00
    variantID_level_return_code_A  3.500000e-02  9.700000e-02  0.000000e+00  0.000000e+00  1.000000e+00
    variantID_level_return_code_B  5.200000e-02  1.110000e-01  0.000000e+00  0.000000e+00  1.000000e+00
    variantID_level_return_code_C  9.000000e-03  5.000000e-02  0.000000e+00  0.000000e+00  1.000000e+00
    variantID_level_return_code_D  4.200000e-02  1.040000e-01  0.000000e+00  0.000000e+00  1.000000e+00

  low-cardinality columns (<=10 uniques):
    Brand_A                          (2 uniq): 0:403,693, 1:7,802
    Brand_B                          (2 uniq): 0:303,460, 1:108,035
    Brand_C                          (2 uniq): 0:405,038, 1:6,457
    Brand_D                          (2 uniq): 0:405,372, 1:6,123
    Brand_E                          (2 uniq): 0:401,847, 1:9,648
    Brand_F                          (2 uniq): 0:403,219, 1:8,276
    Brand_G                          (2 uniq): 0:406,161, 1:5,334
    Brand_I                          (2 uniq): 0:405,633, 1:5,862

==============================================================================
4. LABEL BALANCE (isReturned)
==============================================================================
  event_train: returned(1)=744,867  kept(0)=599,045  pos:neg = 1.24:1  (positive share 55.4%)
  event_test: returned(1)=781,991  kept(0)=650,458  pos:neg = 1.20:1  (positive share 54.6%)

  paper reference pos:neg ratio ~= 1.2:1 (for sanity comparison only)

==============================================================================
5. GRAPH JOIN-KEY INTEGRITY  (critical)
==============================================================================
  event_train   -> customer_train   [customer]: 71,197 unresolved edges (5.30%)  <-- ORPHANS PRESENT
  event_test    -> customer_test    [customer]: 74,559 unresolved edges (5.21%)  <-- ORPHANS PRESENT
  event_train   -> product_train    [product]: 465,772 unresolved edges (34.66%)  <-- ORPHANS PRESENT
  event_test    -> product_test     [product]: 443,216 unresolved edges (30.94%)  <-- ORPHANS PRESENT

  (Every edge endpoint should resolve to a node row. Non-zero orphan
   rates mean edges that reference a customer/product with no feature row.)

==============================================================================
6. TRAIN/TEST ENTITY OVERLAP  (cold-start signal)
==============================================================================
  customers: 764,725 in train, 812,220 in test, 630,519 test-only (77.6% cold-start)
  products: 411,495 in train, 411,544 in test, 6,039 test-only (1.5% cold-start)

  (Test entities absent from train have no graph history -> these are the
   orders the baseline fallback model must score. This % sizes that need.)

==============================================================================
7. RETURN-REASON PROFILE SANITY
==============================================================================
  customer_train: family 'customerId_level_return_code_*' (13 numeric cols) row-sum mean=1.000, share of rows summing ~1.0 = 100.0%
  product_train: family 'variantID_level_return_code_*' (13 numeric cols) row-sum mean=1.000, share of rows summing ~1.0 = 100.0%

  (Reason-code columns are proportions of a customer's/product's past
   returns; rows should sum to ~1 where any returns exist.)

==============================================================================
8. SANITY vs PAPER-REPORTED SCALE
==============================================================================
  event_train rows: 1,343,912  (paper: 939,537)
  event_test  rows: 1,432,449  (paper: 858,526)
  unique customers (train+test): 1,395,244  (paper: 1,084,504)
  unique variants  (train+test): 417,534  (paper: 338,076)

  (Small deviations are fine - the paper's counts are post-cleaning.
   Large gaps mean a different export or an extra preprocessing step.)

==============================================================================
DONE
==============================================================================
  Review the join-integrity and cold-start sections first - they gate
  Phase 1. If both look clean, you're clear to build the baseline.
```
