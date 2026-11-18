# Building the dashboard in Looker Studio (about 30 minutes)

Looker Studio is Google's free dashboard tool (lookerstudio.google.com). It is not the same product as Looker (the paid semantic-layer platform), so on a resume write "Looker Studio".

1. Run `python src/analysis.py` so `output/dashboard_extract.csv` exists.
2. In Looker Studio: **Create > Data source > File Upload**, upload `dashboard_extract.csv`.
3. In the data source, add calculated fields:
   - `Visit rate` = `SUM(visits) / SUM(customers)`
   - `Conversion rate` = `SUM(conversions) / SUM(customers)`
   - `Revenue per customer` = `SUM(revenue) / SUM(customers)`
4. **Create > Report**, then add:
   - Scorecards for Visit rate, Conversion rate, Revenue per customer (dimension: `segment`).
   - A bar chart: dimension `segment`, metric `Visit rate`.
   - A table: rows `dimension_value`, columns `segment`, metric `Visit rate`.
   - A control (drop-down) on `dimension` so viewers can switch between channel, zip code and spend tier.
5. **Share > Manage access > Anyone with the link can view**, copy the link into this README.

Only after the dashboard is live, add "Looker Studio" to your resume and link the dashboard.
