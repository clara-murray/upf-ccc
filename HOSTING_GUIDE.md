# Host the branded-food filter

The app has a small Python server and a read-only SQLite database. Colleagues can use it in a browser once it is deployed; they do not need Python or a local copy of the database.

## Recommended: GitHub + Render

The database is about 506 MB. Keep it out of normal Git history: GitHub blocks individual Git files over 100 MiB. GitHub Release assets can be up to 2 GiB each, so use a Release asset for the database or the packaged ZIP.

1. Download and unzip `branded_food_filter_host_code.zip`.
2. On GitHub, create a **public** repository. Choose **Add file → Upload files**, then upload the unzipped files and `assets` folder. Do not upload the SQLite database.
3. In that repository, choose **Releases → Create a new release**. Name the tag `v1.0` and attach `branded_food_filter_package.zip` as the release file. Publish the release, then copy the download link for that file.
4. On Render, choose **New → Blueprint**, connect the GitHub repository, and create the service. When asked for `METRICS_DB_URL`, paste the release-file download link.
5. When Render finishes, copy its website link and send that to colleagues.

The included Blueprint uses Render's Free web-service plan for a proof of concept. It goes to sleep after 15 minutes without traffic, and the first visit after that can take about a minute to wake. If the app is slow or needs to be available immediately, change to a paid web-service plan in Render. This setup makes both the GitHub repository and Render app public. The app currently has no sign-in. Use a company-approved authenticated host if either must be restricted.

The app binds to Render's `PORT` and `0.0.0.0` settings through the Blueprint. No Python packages are needed.

## Local fallback

Unzip `branded_food_filter_package.zip` on a colleague's computer, open Terminal in the extracted folder, and run:

```bash
python3 food_filter_app.py
```

Then open <http://127.0.0.1:8765>. The hosting package contains the database and logo files.
