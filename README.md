# 📸 Spot Image Viewer

A modern, fast, and user-friendly desktop app to **search, preview, and manage consumer images** from multiple folders — with live folder status, instant previews, and bulk export!  
Developed with ❤️ by Pramod Verma.

---

## 🚀 Features

- 🔍 **Search by Consumer ID or Meter Number**
- 🖼️ **Instant Preview:** See the 3 latest images for any consumer
- 📅 **Date-wise Browsing:** View all available image dates and select to display
- 🖱️ **Click to Zoom, Print, or Save** any image
- 💾 **Bulk Save:** Export all images for a consumer to your Downloads folder in one click
- 🌐 **Network Folder Support:** Add/remove folders; images from online folders are merged and counted live
- 📝 **Meter List Import:** Update meter list from Excel (Consumer ID & Meter Number)
- 🎨 **Themes:** Instantly switch app appearance (light/dark and more)
- 🕑 **Live Folder Status:** See which folders are online/offline in real time
- 🧠 **Search History:** Quick access to recently searched Consumer IDs and Meter Numbers

---

## 🖥️ Screenshots

| Search & Preview | Folder Management | Theme Selector |
|:----------------:|:----------------:|:--------------:|
| ![search](https://img.icons8.com/ios-filled/50/000000/search--v1.png) | ![folder](https://img.icons8.com/ios-filled/50/000000/folder-invoices--v1.png) | ![theme](https://img.icons8.com/ios-filled/50/000000/paint-palette.png) |

---

## ⚡ Quick Start

1. **Clone this repo:**  
   ```bash
   git clone https://github.com/yourusername/SpotImageViewer.git
   cd SpotImageViewer
   ```

2. **Install requirements:**  
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the app:**  
   ```bash
   python SpotImageViewerV3.py
   ```

---

## 📂 Folder Structure

- `SpotImageViewerV3.py` — Main application file
- `C:\spotbillfiles\backup\image` — Default image folder (change in code if needed)
- `C:\spotbillfiles\backup\additional_folders.json` — Stores your added folders
- `C:\spotbillfiles\backup\meter_mapping.json` — Meter mapping (auto-generated)
- `C:\spotbillfiles\backup\image_index.pkl` — Image index (auto-generated)
- `help.pdf` — (Optional) User documentation

---

## 🛠️ Usage Tips

- **Add Folders:** Use the right pane to add/remove network folders. Only online folders are counted.
- **Bulk Save:** Click "Save All" to export all images for a consumer to your Downloads folder, organized by Consumer ID and date.
- **Themes:** Try out different looks from the Theme menu!
- **Meter List:** Update from Excel (Consumer ID in column 1, Meter Number in column 2).
- **Image Counts:** Use the "Image Counts" menu for a detailed breakdown.

---

## 🙋 FAQ

- **Q:** Why is the app slow to start?  
  **A:** The first run builds an index of all images. Subsequent runs are much faster!

- **Q:** How do I update the meter list?  
  **A:** Use the "Update Consumer List" menu and select your Excel file.

- **Q:** Where are images saved?  
  **A:** In your `Downloads/<ConsumerID>/` folder, with filenames as the date.

---

## 👨‍💻 Developer

- **Pramod Verma**
- ERP ID: 90018747

---

## 📝 License

MIT License

---

> **Enjoy using Spot Image Viewer!**  
> For help, see the Help menu
