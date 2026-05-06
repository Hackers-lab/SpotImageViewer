# SpotImageViewer: The Ultimate Utility Verification & Assessment Suite

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-All%20Rights%20Reserved-red.svg)](#license)
[![UI](https://img.shields.io/badge/UI-ttkbootstrap-orange.svg)](https://ttkbootstrap.readthedocs.io/)

**SpotImageViewer** is a high-performance desktop application designed specifically for power utility professionals (WBSEDCL). It transforms the chaotic process of managing field-captured spot imagery into a streamlined, professional workflow, combining rapid search capabilities with a suite of precision assessment tools.

![Home Page](images/home%20page.jpg)

---

## 🌟 Why SpotImageViewer?

In the fast-paced environment of utility management, finding the right data at the right time is critical. SpotImageViewer replaces manual folder navigation and cumbersome spreadsheets with a unified, intelligent workspace.

- **Instant Accessibility:** Retrieve any consumer's image history in milliseconds.
- **Workflow Integration:** Don't just view images—calculate assessments, log remarks, and export data in one go.
- **Modern & Intuitive:** A premium interface with full theme support (including Dark Mode) designed for long working hours.

---

## 🚀 Key Capabilities

### 🔍 Smart Image Discovery & Indexing
Never browse through nested folders again. SpotImageViewer uses a high-performance SQLite engine to index thousands of images across local and network drives.
*   **Rapid Search:** Instantly find images using the unique **9-digit Consumer ID**.
*   **Network Scale:** Effortlessly scan and cache images from shared network locations.
*   **Historical View:** Automatically organizes images by date, providing a clear timeline of consumer spot checks.

![Search Details](images/search%20details.jpg)

### 🖼️ Advanced Verification Workspace
The viewing experience is optimized for inspection and detail.
*   **Precision Zoom & Pan:** Inspect fine details on meters and site conditions with smooth navigation.
*   **Integrated Remarks:** Log site observations directly within the app.
*   **One-Click Actions:** Save, print, or export images and notes instantly.

### 🧮 Professional Calculation Suite
Beyond image viewing, SpotImageViewer is a computational powerhouse for utility assessments.
*   **Theft Assessment Calculator:** A specialized tool for calculating preliminary and final assessments in theft cases, ensuring accuracy and regulatory compliance.

![Theft Calculator](images/theft%20calculator.jpg)

*   **Dynamic Bill Estimator:** Project standard electricity bills based on real-time tariff configurations.

![Bill Calculator](images/bill%20calculator.jpg)

*   **Low Consumption Auditor:** Automatically cross-check usage patterns to identify potential meter issues or abnormalities.

### ⚙️ Intelligent Data Management
*   **Dynamic Tariff Editor:** Keep your calculations up-to-date with a built-in manager for electricity tariff slabs.
*   **Data Portability:** Export your search history and consumer notes to CSV/Excel for reporting.
*   **Secure & Reliable:** Built-in backup routines and database optimizations keep your data safe.

---

## 🎨 A Premium User Experience

SpotImageViewer is built with a focus on ergonomics and aesthetics.
*   **Theme Support:** Switch between **Light (Cosmo)** and **Dark (Darkly)** modes to suit your environment.
*   **Responsive Layout:** A flexible split-pane interface that adjusts to your screen size.
*   **Search History:** Quick-access to your recently viewed consumers.

---

## 🛠️ Built for Performance

*   **Core Logic:** Python 3.8+
*   **Database:** High-performance SQLite with WAL (Write-Ahead Logging).
*   **Imaging:** Optimized Pillow engine for rapid rendering.
*   **UI Framework:** Modern `ttkbootstrap` for a professional, native-feeling application.

---

## 📄 License

Copyright (c) 2026 Pramod Kumar Verma.
All Rights Reserved.

---

> [!NOTE]
> *This documentation is intended for showcase purposes. SpotImageViewer is a proprietary tool developed for utility management optimization.*
