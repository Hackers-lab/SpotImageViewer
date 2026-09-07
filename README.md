# SpotImageViewer: Utility Verification & Assessment Studio

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![UI Engine](https://img.shields.io/badge/UI-PyWebView%20%2B%20WebView2-teal.svg)](https://pywebview.flowrl.com/)
[![Version](https://img.shields.io/badge/Release-v20.1-emerald.svg)](https://github.com/Hackers-lab/SpotImageViewer/releases)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-blue.svg)](#)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](#license)

**SpotImageViewer** is a high-performance desktop verification studio engineered specifically for power utility professionals (WBSEDCL). It transforms the chaotic process of managing field-captured spot meter imagery into a streamlined, high-efficiency workflow—combining millisecond image retrieval with real-time WBSEDCL portal integration, fuzzy candidate lookup, and precision calculation studios.

![SpotImageViewer Home Workspace](images/home%20page.jpg)

---

## 🌟 Why SpotImageViewer?

In modern power utility operations, rapid access to visual meter records and authoritative consumer billing data is critical. SpotImageViewer eliminates folder browsing, disjointed spreadsheets, and manual web portal checks by delivering a unified, intelligent single-page desktop workspace:

- **Instant Visual Discovery:** Index, locate, and preview hundreds of thousands of spot meter photos in milliseconds.
- **Live WBSEDCL Portal Connectivity:** Real-time Outstanding Dues (OSD) scraping and connection status checking right on your viewport.
- **Intelligent Assessment Tools:** Compute WBERC-compliant bills, perform dual-ledger theft assessments, and match records via batch fuzzy lookup.
- **Enterprise Ergonomics:** Modern glassmorphic interface powered by Microsoft Edge WebView2, featuring full Dark & Light mode persistence and VS Code-inspired tool rails.

---

## 🚀 Key Features & Capabilities

### 🔍 Smart Image Discovery & Inspection Viewport
SpotImageViewer indexes local and shared network drives using a high-performance SQLite engine with Write-Ahead Logging (WAL) capable of handling millions of images.

- **Universal Search Engine:** Search instantly by **9-digit Consumer ID**, **Meter Number**, **Mobile Number**, or **Consumer Name** with built-in search history and quick recall.
- **Interactive Inspection Canvas:** Smooth mouse-wheel zoom (up to 500%), click-and-drag panning, 90° rotation, image saving, and direct printing.
- **Timeline Organization:** Automatically organizes photos by reading cycle dates for quick historical trend comparisons.
- **Multi-Photo Overview Grid:** Switch to **Preview All Photos** grid mode to view all historical spot photos for a consumer simultaneously.
- **Photo Filmstrip Dock:** Symmetrical bottom filmstrip with collapsible reel and quick thumbnail navigation.

![Search & Consumer Details](images/search%20details.jpg)

---

### ⚡ Live WBSEDCL OSD & Portal HUD
Stay informed without leaving your workflow. The embedded floating HUD card queries live portal data in the background:
- **Connection Status:** Displays clean live status indicators (**Connected**, **Deemed**, **Disconnected**).
- **Outstanding Dues Breakdown:** Instant extraction of total dues, unpaid bill balance, and Late Payment Surcharge (LPSC).
- **Smart Office Location:** Automatically parses and standardizes office locations (stripping redundant CCC prefixes) with hover tooltip support.

---

### 🔍 Batch & Manual Fuzzy Matching Engine
Match field records, voter lists, or survey sheets against the utility meter mapping database using weighted token and string similarity algorithms.

- **Automated Fuzzy Matching:** Compare names and service addresses with configurable threshold scoring (0.00 – 1.00) and top-N candidate ranking.
- **Relative / Ancestor Recognition:** Detects family references (e.g., father, husband, S/O, W/O) for high-confidence identification.
- **1-Click Live OSD Verification:** Directly query live portal outstanding dues for matched candidates within the results table.
- **Interactive Ad-Hoc Lookup:** Test individual queries on the fly without uploading external files.
- **Excel Import & Export:** Process `.xlsx` spreadsheets and export matched candidate reports with complete audit trails.

![Batch Fuzzy Lookup Studio](images/fuzzy%20lookup.jpg)

---

### 🧮 WBERC Bill Calculator Studio
A comprehensive, regulatory-accurate tariff engine configured for official West Bengal Electricity Regulatory Commission (WBERC) rules.

- **Symmetrical Time-of-Day (TOD):** Normal, Peak, and Off-Peak consumption modeling.
- **Tiered Tariff Slabs:** Automated tiered energy charges and electricity duty (ED) calculations.
- **Government Relief & Subsidies:** Accurate pro-rata calculation of domestic lifelines and subsidy ceilings (≤ 300 units/month).
- **Comprehensive Surcharges & Rebates:** Phase-based meter rent, timely payment rebates, special rebates, and minimum charge protections.
- **Pro-Rata Date Range Picker:** Interactive calendar pickers with automatic day-count and fractional slab adjustments.

![Bill Calculator Studio](images/bill%20calculator.jpg)

---

### ⚖️ Dual-Ledger Theft Assessment Studio
A specialized assessment tool for calculating provisional and final statutory electricity theft assessments under regulatory standards.

- **Provisional vs. Final Assessment:** Side-by-side ledger comparing connected load, diversity factors, working days, and hours.
- **Statutory Relief Limit (25%):** Visual compliance indicator that monitors and warns if final assessment relief exceeds statutory caps.
- **Net Assessment Rounding:** Automatic ceiling of final payable assessment to the nearest integer rupee.
- **Quick Consumption Estimator:** Rapid pro-rata estimation based on recognized equipment capacity.

![Theft Assessment Calculator](images/theft%20calculator.jpg)

---

### 📊 Low Consumption Audit & Tariff Management
- **Low Consumption Auditor:** Scan consumer billing records to detect meter anomalies, zero-consumption cycles, or suspected meter tampering.
- **Dynamic Tariff Editor:** Full CRUD manager for electricity slabs, fixed charges, and load factors—keeping calculations updated across tariff revisions without code modification.
- **Multi-Directory Network Manager:** Manage primary and secondary photo repositories with real-time online/offline accessibility status and background re-indexing.

---

## 🎨 Modern Workspace Ergonomics

SpotImageViewer provides a distraction-free, professional environment designed for intensive daily operation:

* **Persistent Dark & Light Themes:** Toggle between dark and light themes with preference saved directly into the SQLite database.
* **Collapsible Accordion Dock:** Right inspector panel with smooth tab switching between Consumer Details, Billing Cycles, and Site Notes/Remarks.
* **Non-Blocking Architecture:** All heavy indexing, fuzzy processing, and live portal scraping run asynchronously in background threads.
* **Silent In-App Auto-Updater:** Automatically checks for new releases on launch with 1-click silent installer execution.

---

## 🛠️ Technical Architecture

| Component | Technology |
|---|---|
| **Core Runtime** | Python 3.11+ |
| **GUI Framework** | PyWebView with Microsoft Edge WebView2 runtime |
| **Frontend UI** | Modern HTML5 Single Page Application (SPA) with Tailwind CSS & Lucide Icons |
| **Database** | Embedded SQLite3 with Write-Ahead Logging (WAL) mode |
| **Imaging Engine** | Pillow (PIL) image processing with dynamic thumbnail caching |
| **PDF Extraction** | `pypdf` stream extractor for official WBSEDCL certificates |
| **Fuzzy Matching** | `rapidfuzz` & `thefuzz` string metrics |
| **Packaging** | PyInstaller binary bundle with Inno Setup modern installer |

---

## 📄 License

Copyright (c) 2026 Pramod Kumar Verma.  
All Rights Reserved.

---

> [!NOTE]
> *SpotImageViewer is an enterprise utility verification studio developed for power distribution management optimization.*
