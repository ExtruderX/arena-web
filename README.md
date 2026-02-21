# Arena Web (iPad Safari)

This repo is meant to be deployed to **GitHub Pages** automatically using **GitHub Actions + pygbag**.

## Quick Start (NO git needed)
1. Create a new GitHub repo (Public).
2. Upload ALL files/folders from this project to the repo root.

### Important (macOS Finder hides `.github`)
If you upload from a Mac, Finder may hide the `.github` folder.
- In Finder press **Cmd + Shift + .** (dot) to show hidden files.
- Then upload the `.github` folder too.

If you already uploaded everything BUT `.github`, you can fix it without reupload:
- GitHub repo → **Add file → Create new file**
- File name: `.github/workflows/deploy.yml`
- Paste the contents from `COPY_PASTE_WORKFLOW.txt`
- Commit.

## Deploy
- Push/commit to `main` triggers Actions.
- Wait for Actions to finish (green check).
- Repo Settings → Pages:
  - Source: Deploy from a branch
  - Branch: `gh-pages` / root

Then your site will be live at:
`https://<username>.github.io/<repo>/`

## Notes
- Saves are stored in browser localStorage (so iPad keeps progress).
- Controls: keyboard/mouse recommended (Bluetooth on iPad).
