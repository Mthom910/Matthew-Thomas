import pandas as pd, warnings
warnings.filterwarnings('ignore')

# Load OrdersCount - already one row per base ref
oc = pd.read_excel(
    r'C:\Users\matth\Downloads\Sales by Representative - 2026-06-29T113025.017.xlsx',
    sheet_name='OrdersCount', header=0
)
oc.columns = ['Representative','BusinessUnit','Company','Contact','OrderDate',
              'Job','SubJob','ProductName','Qty','EstCost','RRP','SalePrice',
              'EstMargin','EstMarginPct','CostPrice','MarginAmt','MarginPct',
              'GST','SaleIncGST','AmountPaid']
oc = oc[oc['Job'].notna() & (oc['Job'].astype(str).str.startswith('J'))]
oc['SalePrice'] = pd.to_numeric(oc['SalePrice'], errors='coerce').fillna(0)
oc['OrderDate'] = pd.to_datetime(oc['OrderDate'], errors='coerce')

# Filter to H1 2026
h1 = oc[(oc['OrderDate'] >= '2026-01-01') & (oc['OrderDate'] <= '2026-06-30')]
print(f"Total orders in file: {len(oc)}")
print(f"H1 2026 orders (Jan-Jun): {len(h1)}")
print(f"H1 2026 orders >= $5,000: {(h1['SalePrice'] >= 5000).sum()}")
print(f"H1 2026 total Sale Price: ${h1['SalePrice'].sum():,.2f}")
print(f"H1 2026 >=5k total Sale Price: ${h1.loc[h1['SalePrice']>=5000,'SalePrice'].sum():,.2f}")
print()

# Also check the Orders sheet to understand the SalePrice field
orders = pd.read_excel(
    r'C:\Users\matth\Downloads\Sales by Representative - 2026-06-29T113025.017.xlsx',
    sheet_name='Orders', header=0
)
orders.columns = ['Representative','BusinessUnit','Company','Contact','OrderDate',
                  'Job','ProductName','Qty','EstCost','RRP','SalePrice',
                  'EstMargin','EstMarginPct','CostPrice','MarginAmt','MarginPct',
                  'GST','SaleIncGST','AmountPaid']
orders = orders[orders['Job'].notna() & (orders['Job'].astype(str).str.contains('-'))]
orders['SalePrice'] = pd.to_numeric(orders['SalePrice'], errors='coerce').fillna(0)
orders['OrderDate'] = pd.to_datetime(orders['OrderDate'], errors='coerce')
orders['BaseRef'] = orders['Job'].str.replace(r'-\d+$','',regex=True)

# Sum by base ref to compare with OrdersCount
by_base = orders.groupby('BaseRef').agg(
    TotalSalePrice=('SalePrice','sum'),
    OrderDate=('OrderDate','first')
).reset_index()

o_h1 = by_base[(by_base['OrderDate'] >= '2026-01-01') & (by_base['OrderDate'] <= '2026-06-30')]
print(f"Orders sheet - unique base refs in H1 2026: {len(o_h1)}")
print(f"Orders sheet - base refs >= $5k combined: {(o_h1['TotalSalePrice'] >= 5000).sum()}")
print(f"Orders sheet - total sale price: ${o_h1['TotalSalePrice'].sum():,.2f}")
