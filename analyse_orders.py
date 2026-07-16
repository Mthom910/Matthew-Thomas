import pandas as pd, warnings
warnings.filterwarnings('ignore')

df = pd.read_excel(
    r'C:\Users\matth\Downloads\Sales by Representative - 2026-06-29T113025.017.xlsx',
    sheet_name='OrdersCount', header=0
)
df.columns = ['Representative','BusinessUnit','Company','Contact','OrderDate',
              'Job','SubJob','ProductName','Qty','EstCost','RRP','SalePrice',
              'EstMargin','EstMarginPct','CostPrice','MarginAmt','MarginPct',
              'GST','SaleIncGST','AmountPaid']
df = df[df['Job'].notna() & (df['Job'].astype(str) != 'nan')]
df['SalePrice'] = pd.to_numeric(df['SalePrice'], errors='coerce').fillna(0)
df['EstCost']   = pd.to_numeric(df['EstCost'],   errors='coerce').fillna(0)

# Sum by base Job reference
by_job = df.groupby('Job').agg(
    TotalSalePrice=('SalePrice','sum'),
    TotalCost=('EstCost','sum'),
    Representative=('Representative','first'),
    OrderDate=('OrderDate','first'),
).reset_index()

over5k = by_job[by_job['TotalSalePrice'] >= 5000].copy()
print(f'Total unique base-ref jobs: {len(by_job)}')
print(f'Jobs with Sale Price >= $5,000: {len(over5k)}')
print(f'Total Sale Price of >=5k jobs: ${over5k["TotalSalePrice"].sum():,.2f}')
print(f'Total Est Cost of >=5k jobs:   ${over5k["TotalCost"].sum():,.2f}')
print()

# Check what the sub-job-level Sale Price represents
print('Sample sub-job entries for J0101260:')
sample = df[df['Job'] == 'J0101260'][['Job','SubJob','ProductName','SalePrice','EstCost']].head(10)
print(sample.to_string())
print()

# Check total rows vs unique jobs
print(f'Total line rows in OrdersCount: {len(df)}')
print(f'Unique base refs: {df["Job"].nunique()}')

# Show top 10 jobs by sale price
print()
print('Top 10 orders by Sale Price:')
print(over5k.nlargest(10,'TotalSalePrice')[['Job','Representative','TotalSalePrice','TotalCost']].to_string())
