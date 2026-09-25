# Branded food filter app

This local browser app compares a definition against US branded-food products. It shows the overall share, four food-category shares, and shares for PepsiCo, Tyson Foods, Kraft Heinz, General Mills, and Mars Inc.

## Run the app

You need Python 3. No additional Python packages are required.

From Terminal, change to the folder containing these files and run:

```bash
python3 food_filter_app.py
```

Open <http://127.0.0.1:8765> in a browser. Stop the app with **Ctrl+C**.

Click **Calculate** after changing the sliders or AND/OR controls. Results do not update while you drag.

## Share with colleagues

Share these files and the logo folder in a company-approved shared folder:

- `food_filter_app.py`
- `food_filter_definitions.py`
- `branded_food_filter_metrics.sqlite3`
- `FOOD_FILTER_APP_README.md`
- `assets/brand-logos/` (the folder with all five SVG logos)

The SQLite metrics file is about 506 MB. Each colleague can copy the files to a folder on their computer and run the command above. The original `branded_food_long.sqlite3` and `prepare_food_filter_metrics.py` are not needed to run the app.

For a hosted browser link, see [HOSTING_GUIDE.md](HOSTING_GUIDE.md). The complete share package is `branded_food_filter_package.zip`.

## What the filters do

- Each slider has an unticked Include checkbox and an AND/OR toggle that defaults to AND. Check Include to enable that slider and use its threshold.
- Checked thresholds combine from top to bottom within each section, following each slider's AND/OR setting.
- Products matching the checked nutrient thresholds are excluded from the UPF share: first-section matches AND NOT nutrient-section matches.
- If no first-section checkboxes are checked, the definition includes no products.
- The two sections are combined as: first-section match AND NOT nutrient-section match.
- Sliders start at zero. Changes are calculated only after clicking **Calculate**.
- Food-category cards cover bread, biscuits and cookies, sausages, and chips and crisps.
- Company cards group matching `brand_owner` name variants for PepsiCo, Tyson Foods, Kraft Heinz, General Mills, and Mars Inc.
- Selected macro values outside 0–100 on the USDA per-100-unit basis were excluded when the metrics file was prepared. The original source database was not changed.
