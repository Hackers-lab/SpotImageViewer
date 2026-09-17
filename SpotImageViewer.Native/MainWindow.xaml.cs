using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Animation;
using System.Windows.Media.Imaging;
using System.Windows.Shapes;
using Microsoft.Win32;
using SpotImageViewer.Native.Core;
using Path = System.IO.Path;

namespace SpotImageViewer.Native;

public partial class MainWindow : Window
{
    private List<ImageItem> _currentImages = new();
    private ConsumerProfile? _currentProfile;
    private int _currentImageIndex = -1;
    private string _currentImagePath = "";

    // Image pan & zoom state
    private bool _isPanning = false;
    private Point _lastPanPoint;
    private bool _sidebarExplicitlyCollapsed = false;

    public MainWindow()
    {
        InitializeComponent();
        Logger.Log("APP", "Native WPF MainWindow initialized with 1:1 Studio UI");

        Loaded += MainWindow_Loaded;
        PreviewKeyDown += MainWindow_PreviewKeyDown;
    }

    private async void MainWindow_Loaded(object sender, RoutedEventArgs e)
    {
        try
        {
            txtStatusMessage.Text = "Initializing database and image index...";
            var sw = Stopwatch.StartNew();

            // 1. Load App Info (image counts, folders)
            await RefreshAppInfoAsync().ConfigureAwait(true);

            // 2. Populate Tariff Categories
            PopulateTariffCategories();

            sw.Stop();
            txtStatusMessage.Text = $"Ready • Database loaded in {sw.ElapsedMilliseconds}ms";
            Logger.Log("APP", $"MainWindow fully loaded and ready in {sw.ElapsedMilliseconds}ms");
        }
        catch (Exception ex)
        {
            Logger.LogError("APP", "Error during MainWindow_Loaded", ex);
            txtStatusMessage.Text = "Error during startup: " + ex.Message;
        }
    }

    private async Task RefreshAppInfoAsync()
    {
        try
        {
            var appInfo = await Database.Instance.GetAppInfoAsync().ConfigureAwait(true);
            txtImageCountHeader.Text = $"{appInfo.AvailableImages:N0}";

            bool allOnline = appInfo.Folders.All(f => f.Accessible);
            dotStatus.Fill = allOnline
                ? (SolidColorBrush)FindResource("BrushAccentEmerald")
                : (SolidColorBrush)FindResource("BrushAccentAmber");

            long offlineCount = appInfo.TotalImages - appInfo.AvailableImages;
            badgeFolderStatus.ToolTip = allOnline
                ? $"All folders online ({appInfo.TotalImages:N0} spot bill photos indexed)"
                : $"Warning: {offlineCount:N0} photos are in offline network shares. Click to inspect.";

            // Also refresh settings tab folder list
            RenderSettingsFolders(appInfo.Folders);
        }
        catch (Exception ex)
        {
            Logger.LogError("APP", "RefreshAppInfoAsync failed", ex);
        }
    }

    private void PopulateTariffCategories()
    {
        var categories = BillingEngine.GetTariffCategories();
        cbTariffCategory.ItemsSource = categories;
        if (categories.Count > 0)
        {
            cbTariffCategory.SelectedIndex = 0;
        }
    }

    // =========================================================================
    // SIDEBAR RAIL ANIMATION & TOGGLE
    // =========================================================================
    private void SidebarCollapseBtn_Click(object sender, RoutedEventArgs e)
    {
        _sidebarExplicitlyCollapsed = !_sidebarExplicitlyCollapsed;
        AnimateSidebar(_sidebarExplicitlyCollapsed ? 44 : 176);
    }

    private void SidebarRail_MouseEnter(object sender, MouseEventArgs e)
    {
        if (!_sidebarExplicitlyCollapsed)
        {
            AnimateSidebar(176);
        }
    }

    private void SidebarRail_MouseLeave(object sender, MouseEventArgs e)
    {
        if (!_sidebarExplicitlyCollapsed)
        {
            AnimateSidebar(44);
        }
    }

    private void AnimateSidebar(double targetWidth)
    {
        var anim = new DoubleAnimation
        {
            To = targetWidth,
            Duration = TimeSpan.FromMilliseconds(160),
            EasingFunction = new CubicEase { EasingMode = EasingMode.EaseOut }
        };
        sidebarRail.BeginAnimation(WidthProperty, anim);
    }

    // =========================================================================
    // NAVIGATION TABS
    // =========================================================================
    private void NavTab_Checked(object sender, RoutedEventArgs e)
    {
        if (panelViewer == null) return;

        panelViewer.Visibility = rbTabViewer.IsChecked == true ? Visibility.Visible : Visibility.Collapsed;
        panelTariff.Visibility = (rbTabTariff.IsChecked == true || rbTabTheft.IsChecked == true || rbTabDcrc?.IsChecked == true) ? Visibility.Visible : Visibility.Collapsed;
        panelFuzzy.Visibility = rbTabFuzzy.IsChecked == true ? Visibility.Visible : Visibility.Collapsed;
        panelAudit.Visibility = rbTabAudit.IsChecked == true ? Visibility.Visible : Visibility.Collapsed;
        panelLiveOsd.Visibility = rbTabLiveOsd.IsChecked == true ? Visibility.Visible : Visibility.Collapsed;
        panelSettings.Visibility = rbTabSettings.IsChecked == true ? Visibility.Visible : Visibility.Collapsed;
    }

    private void SwitchToTab(RadioButton tab)
    {
        tab.IsChecked = true;
    }

    // =========================================================================
    // KEYBOARD SHORTCUTS
    // =========================================================================
    private void MainWindow_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        // Ctrl+B toggles sidebar
        if (Keyboard.Modifiers == ModifierKeys.Control && e.Key == Key.B)
        {
            e.Handled = true;
            SidebarCollapseBtn_Click(sender, e);
            return;
        }

        // Ignore shortcuts if user is typing in a text input
        if (Keyboard.FocusedElement is TextBox && Keyboard.FocusedElement != txtGlobalSearch)
        {
            return;
        }

        // '/' to focus global search
        if (e.Key == Key.OemQuestion && !(Keyboard.FocusedElement is TextBox))
        {
            e.Handled = true;
            txtGlobalSearch.Focus();
            txtGlobalSearch.SelectAll();
            return;
        }

        // Left / Right arrow keys to switch photo
        if (imgMain.Visibility == Visibility.Visible && _currentImages.Count > 1)
        {
            if (e.Key == Key.Left)
            {
                e.Handled = true;
                CycleImage(-1);
            }
            else if (e.Key == Key.Right)
            {
                e.Handled = true;
                CycleImage(1);
            }
        }

        // Escape to clear search
        if (e.Key == Key.Escape)
        {
            e.Handled = true;
            BtnClearSearch_Click(sender, e);
        }
    }

    // =========================================================================
    // CONSUMER SEARCH & SELECTION
    // =========================================================================
    private void TxtGlobalSearch_TextChanged(object sender, TextChangedEventArgs e)
    {
        btnClearSearch.Visibility = string.IsNullOrWhiteSpace(txtGlobalSearch.Text)
            ? Visibility.Collapsed
            : Visibility.Visible;
    }

    private async void TxtGlobalSearch_KeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter)
        {
            e.Handled = true;
            await ExecuteSearchAsync(txtGlobalSearch.Text).ConfigureAwait(true);
        }
    }

    private async void BtnSearch_Click(object sender, RoutedEventArgs e)
    {
        await ExecuteSearchAsync(txtGlobalSearch.Text).ConfigureAwait(true);
    }

    private async Task ExecuteSearchAsync(string query)
    {
        query = query?.Trim() ?? "";
        if (string.IsNullOrEmpty(query)) return;

        txtStatusMessage.Text = $"Searching for '{query}'...";
        var sw = Stopwatch.StartNew();

        try
        {
            var results = await Database.Instance.SearchConsumerAsync(query).ConfigureAwait(true);
            if (results.Count == 0)
            {
                // If query is 9 digits, try direct consumer images lookup anyway
                if (query.Length == 9 && query.All(char.IsDigit))
                {
                    await LoadConsumerAsync(query, null).ConfigureAwait(true);
                    return;
                }

                txtStatusMessage.Text = $"No consumer found matching '{query}'.";
                MessageBox.Show($"No consumer found matching '{query}'.", "Not Found", MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            // If single result or exact CID match, load directly
            var match = results.FirstOrDefault(r => r.ConsumerId == query) ?? results[0];
            await LoadConsumerAsync(match.ConsumerId, match).ConfigureAwait(true);

            sw.Stop();
            txtStatusMessage.Text = $"Consumer {match.ConsumerId} loaded in {sw.ElapsedMilliseconds}ms";
        }
        catch (Exception ex)
        {
            Logger.LogError("SEARCH", $"Error searching '{query}'", ex);
            txtStatusMessage.Text = "Search error: " + ex.Message;
        }
    }

    public async Task LoadConsumerAsync(string consumerId, ConsumerProfile? profile)
    {
        SwitchToTab(rbTabViewer);
        txtGlobalSearch.Text = consumerId;

        // 1. Fetch images and profile from database
        var (p, images) = await Database.Instance.GetConsumerImagesAsync(consumerId).ConfigureAwait(true);
        _currentProfile = profile ?? p ?? new ConsumerProfile { ConsumerId = consumerId };
        _currentImages = images;

        // 2. Populate Right Details Panel
        profileName.Text = string.IsNullOrWhiteSpace(_currentProfile.Name) ? "(Name Not Available)" : _currentProfile.Name;
        profileCid.Text = _currentProfile.ConsumerId;
        profileMeter.Text = string.IsNullOrWhiteSpace(_currentProfile.MeterNo) ? "-" : _currentProfile.MeterNo;
        profileMobile.Text = string.IsNullOrWhiteSpace(_currentProfile.MobileNumber) ? "-" : _currentProfile.MobileNumber;
        profileLoadClass.Text = $"{_currentProfile.ContractualLoad ?? "-"} kVA • {_currentProfile.Class ?? "-"}";
        profileAddress.Text = string.IsNullOrWhiteSpace(_currentProfile.Address) ? "(Address Not Available)" : _currentProfile.Address;
        txtSearchResultCount.Text = $"{_currentImages.Count} photos";

        // Query Live OSD in background for HUD card
        _ = FetchLiveOsdForHudAsync(consumerId);

        // 3. Render Available Dates List in Right Dock
        panelPhotoChips.Children.Clear();
        if (_currentImages.Count == 0)
        {
            panelPhotoChips.Children.Add(new TextBlock
            {
                Text = "No spot bill photos on disk",
                FontSize = 10.5,
                Foreground = (Brush)FindResource("BrushAccentAmber"),
                Margin = new Thickness(4, 2, 4, 2)
            });

            // Show empty placeholder in canvas
            panelWelcome.Visibility = Visibility.Visible;
            imgMain.Visibility = Visibility.Collapsed;
            singleViewControls.Visibility = Visibility.Collapsed;
            btnCanvasPrev.Visibility = Visibility.Collapsed;
            btnCanvasNext.Visibility = Visibility.Collapsed;
            imgDateTagContainer.Visibility = Visibility.Collapsed;
        }
        else
        {
            for (int i = 0; i < _currentImages.Count; i++)
            {
                var img = _currentImages[i];
                int idx = i;

                var chipBorder = new Border
                {
                    Background = (Brush)FindResource("BrushSurface0"),
                    BorderBrush = (Brush)FindResource("BrushBorder"),
                    BorderThickness = new Thickness(1),
                    CornerRadius = new CornerRadius(6),
                    Padding = new Thickness(8, 6, 8, 6),
                    Margin = new Thickness(0, 0, 0, 4),
                    Cursor = Cursors.Hand
                };

                var sp = new StackPanel { Orientation = Orientation.Horizontal };
                sp.Children.Add(new TextBlock
                {
                    Text = "📅 " + img.DateFormatted,
                    FontSize = 11,
                    FontWeight = FontWeights.SemiBold,
                    Foreground = (Brush)FindResource("BrushTextPrimary")
                });
                sp.Children.Add(new TextBlock
                {
                    Text = $" ({img.Filename})",
                    FontSize = 9.5,
                    Foreground = (Brush)FindResource("BrushTextMuted"),
                    Margin = new Thickness(6, 1, 0, 0)
                });
                chipBorder.Child = sp;

                chipBorder.MouseDown += (s, e) => DisplayImage(idx);
                panelPhotoChips.Children.Add(chipBorder);
            }

            // Display first photo
            DisplayImage(0);
        }
    }

    private async Task FetchLiveOsdForHudAsync(string cid)
    {
        try
        {
            liveOsdHud.Visibility = Visibility.Visible;
            txtLiveOsdStatus.Text = "Querying...";
            txtLiveOsdTotalDues.Text = "₹ ...";

            var res = await LiveOsdService.Instance.FetchLiveOsdAsync(cid).ConfigureAwait(true);
            txtLiveOsdStatus.Text = string.IsNullOrWhiteSpace(res.ConnectionStatus) ? "Active" : res.ConnectionStatus;
            txtLiveOsdStatus.Foreground = res.ConnectionStatus.Contains("Disconn", StringComparison.OrdinalIgnoreCase)
                ? (Brush)FindResource("BrushAccentRose")
                : (Brush)FindResource("BrushAccentEmerald");

            txtLiveOsdTotalDues.Text = $"₹ {res.TotalDues:N2}";
            txtLiveOsdUnpaidLpsc.Text = $"₹ {res.Osd:N2} + ₹ {res.Lpsc:N2}";
            txtLiveOsdOffice.Text = string.IsNullOrWhiteSpace(res.Office) ? "KUSHIDA CCC" : res.Office;
        }
        catch (Exception ex)
        {
            txtLiveOsdStatus.Text = "Offline";
            txtLiveOsdStatus.Foreground = (Brush)FindResource("BrushAccentRose");
            txtLiveOsdTotalDues.Text = "₹ 0.00";
            Logger.LogError("HUD_OSD", "Failed to query live OSD for HUD", ex);
        }
    }

    private void BtnClearSearch_Click(object sender, RoutedEventArgs e)
    {
        txtGlobalSearch.Text = "";
        _currentImages.Clear();
        _currentProfile = null;
        _currentImageIndex = -1;
        _currentImagePath = "";

        // Reset Right Dock
        profileName.Text = "No consumer selected";
        profileCid.Text = "-";
        profileMeter.Text = "-";
        profileMobile.Text = "-";
        profileLoadClass.Text = "-";
        profileAddress.Text = "-";
        txtSearchResultCount.Text = "0 photos";
        panelPhotoChips.Children.Clear();

        // Switch to Welcome screen
        imgMain.Source = null;
        imgMain.Visibility = Visibility.Collapsed;
        singleViewControls.Visibility = Visibility.Collapsed;
        btnCanvasPrev.Visibility = Visibility.Collapsed;
        btnCanvasNext.Visibility = Visibility.Collapsed;
        imgDateTagContainer.Visibility = Visibility.Collapsed;
        liveOsdHud.Visibility = Visibility.Collapsed;
        panelWelcome.Visibility = Visibility.Visible;
        txtStatusMessage.Text = "Ready";
    }

    // =========================================================================
    // IMAGE RENDERING & PAN/ZOOM/TRANSFORM
    // =========================================================================
    private void DisplayImage(int index)
    {
        if (index < 0 || index >= _currentImages.Count) return;
        _currentImageIndex = index;
        var item = _currentImages[index];
        _currentImagePath = item.FullPath;

        try
        {
            if (File.Exists(item.FullPath))
            {
                var bmp = new BitmapImage();
                bmp.BeginInit();
                bmp.CacheOption = BitmapCacheOption.OnLoad; // releases file lock
                bmp.UriSource = new Uri(item.FullPath, UriKind.Absolute);
                bmp.EndInit();
                bmp.Freeze();

                imgMain.Source = bmp;
                imgMain.Visibility = Visibility.Visible;
                panelWelcome.Visibility = Visibility.Collapsed;
                singleViewControls.Visibility = Visibility.Visible;
                imgDateTagContainer.Visibility = Visibility.Visible;
                txtImgDateTag.Text = item.DateFormatted;

                btnCanvasPrev.Visibility = _currentImages.Count > 1 ? Visibility.Visible : Visibility.Collapsed;
                btnCanvasNext.Visibility = _currentImages.Count > 1 ? Visibility.Visible : Visibility.Collapsed;

                txtStatusMessage.Text = $"Displaying {item.Filename} ({bmp.PixelWidth}×{bmp.PixelHeight}px)";
            }
            else
            {
                imgMain.Source = null;
                txtStatusMessage.Text = $"File offline or inaccessible: {item.FullPath}";
            }

            // Reset pan/zoom
            ResetImageTransform();

            // Highlight selected chip in Right Dock
            for (int i = 0; i < panelPhotoChips.Children.Count; i++)
            {
                if (panelPhotoChips.Children[i] is Border b)
                {
                    b.BorderBrush = (i == index)
                        ? (Brush)FindResource("BrushAccentSky")
                        : (Brush)FindResource("BrushBorder");
                    b.Background = (i == index)
                        ? (Brush)FindResource("BrushSurface2")
                        : (Brush)FindResource("BrushSurface0");
                }
            }
        }
        catch (Exception ex)
        {
            Logger.LogError("IMAGE", $"Failed to load image '{item.FullPath}'", ex);
            txtStatusMessage.Text = "Error loading image: " + ex.Message;
        }
    }

    private void CycleImage(int delta)
    {
        if (_currentImages.Count == 0) return;
        int next = _currentImageIndex + delta;
        if (next < 0) next = _currentImages.Count - 1;
        if (next >= _currentImages.Count) next = 0;
        DisplayImage(next);
    }

    private void BtnCanvasPrev_Click(object sender, RoutedEventArgs e) => CycleImage(-1);
    private void BtnCanvasNext_Click(object sender, RoutedEventArgs e) => CycleImage(1);

    private void ResetImageTransform()
    {
        imgScaleTransform.ScaleX = 1.0;
        imgScaleTransform.ScaleY = 1.0;
        imgTranslateTransform.X = 0;
        imgTranslateTransform.Y = 0;
        imgRotateTransform.Angle = 0;
        txtZoomLevel.Text = "100%";
    }

    private void BtnZoomIn_Click(object sender, RoutedEventArgs e)
    {
        imgScaleTransform.ScaleX *= 1.25;
        imgScaleTransform.ScaleY *= 1.25;
        txtZoomLevel.Text = $"{Math.Round(imgScaleTransform.ScaleX * 100)}%";
    }

    private void BtnZoomOut_Click(object sender, RoutedEventArgs e)
    {
        imgScaleTransform.ScaleX = Math.Max(0.1, imgScaleTransform.ScaleX * 0.8);
        imgScaleTransform.ScaleY = Math.Max(0.1, imgScaleTransform.ScaleY * 0.8);
        txtZoomLevel.Text = $"{Math.Round(imgScaleTransform.ScaleX * 100)}%";
    }

    private void BtnZoomFit_Click(object sender, RoutedEventArgs e) => ResetImageTransform();

    private void BtnRotate_Click(object sender, RoutedEventArgs e)
    {
        imgRotateTransform.Angle = (imgRotateTransform.Angle + 90) % 360;
    }

    private void BtnOpenExternal_Click(object sender, RoutedEventArgs e)
    {
        if (string.IsNullOrEmpty(_currentImagePath) || !File.Exists(_currentImagePath))
        {
            MessageBox.Show("Image file is not accessible on disk.", "Cannot Open", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }
        try
        {
            Process.Start(new ProcessStartInfo(_currentImagePath) { UseShellExecute = true });
        }
        catch (Exception ex)
        {
            MessageBox.Show("Failed to open image in external viewer: " + ex.Message);
        }
    }

    private void BtnPrint_Click(object sender, RoutedEventArgs e)
    {
        if (imgMain.Source == null) return;
        var dlg = new PrintDialog();
        if (dlg.ShowDialog() == true)
        {
            dlg.PrintVisual(imgMain, "Spot Bill Image");
        }
    }

    private void BtnSaveImage_Click(object sender, RoutedEventArgs e)
    {
        if (string.IsNullOrEmpty(_currentImagePath) || !File.Exists(_currentImagePath))
        {
            MessageBox.Show("No active photo loaded to save.", "Info", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        var sfd = new SaveFileDialog
        {
            FileName = Path.GetFileName(_currentImagePath),
            Filter = "JPEG Image (*.jpg)|*.jpg|All Files (*.*)|*.*"
        };
        if (sfd.ShowDialog() == true)
        {
            File.Copy(_currentImagePath, sfd.FileName, true);
            txtStatusMessage.Text = $"Saved image to {sfd.FileName}";
        }
    }

    // Mouse Pan & Zoom
    private void BorderImageContainer_MouseWheel(object sender, MouseWheelEventArgs e)
    {
        double factor = e.Delta > 0 ? 1.15 : 0.87;
        imgScaleTransform.ScaleX = Math.Max(0.05, imgScaleTransform.ScaleX * factor);
        imgScaleTransform.ScaleY = Math.Max(0.05, imgScaleTransform.ScaleY * factor);
        txtZoomLevel.Text = $"{Math.Round(imgScaleTransform.ScaleX * 100)}%";
    }

    private void BorderImageContainer_MouseDown(object sender, MouseButtonEventArgs e)
    {
        if (e.LeftButton == MouseButtonState.Pressed)
        {
            _isPanning = true;
            _lastPanPoint = e.GetPosition(borderImageContainer);
            borderImageContainer.CaptureMouse();
        }
    }

    private void BorderImageContainer_MouseMove(object sender, MouseEventArgs e)
    {
        if (_isPanning)
        {
            Point cur = e.GetPosition(borderImageContainer);
            imgTranslateTransform.X += (cur.X - _lastPanPoint.X);
            imgTranslateTransform.Y += (cur.Y - _lastPanPoint.Y);
            _lastPanPoint = cur;
        }
    }

    private void BorderImageContainer_MouseUp(object sender, MouseButtonEventArgs e)
    {
        if (_isPanning)
        {
            _isPanning = false;
            borderImageContainer.ReleaseMouseCapture();
        }
    }

    // =========================================================================
    // COPY TO CLIPBOARD BUTTONS
    // =========================================================================
    private void CopyToClipboard(string text, string label)
    {
        if (string.IsNullOrWhiteSpace(text) || text == "-") return;
        Clipboard.SetText(text);
        txtStatusMessage.Text = $"Copied {label}: {text}";
    }

    private void CopyName_Click(object sender, RoutedEventArgs e) => CopyToClipboard(profileName.Text, "Name");
    private void CopyCid_Click(object sender, RoutedEventArgs e) => CopyToClipboard(profileCid.Text, "Consumer ID");
    private void CopyMeter_Click(object sender, RoutedEventArgs e) => CopyToClipboard(profileMeter.Text, "Meter No");
    private void CopyMobile_Click(object sender, RoutedEventArgs e) => CopyToClipboard(profileMobile.Text, "Mobile");
    private void CopyLoad_Click(object sender, RoutedEventArgs e) => CopyToClipboard(profileLoadClass.Text, "Load/Class");
    private void CopyAddress_Click(object sender, RoutedEventArgs e) => CopyToClipboard(profileAddress.Text, "Address");

    // =========================================================================
    // NOTES & REMARKS
    // =========================================================================
    private void BtnSaveNote_Click(object sender, RoutedEventArgs e)
    {
        string status = (cbNoteCategory.SelectedItem as ComboBoxItem)?.Content?.ToString() ?? "OK";
        string remarks = txtNoteRemarks.Text.Trim();
        txtStatusMessage.Text = $"Note saved: [{status}] {remarks}";
        MessageBox.Show($"Remarks saved successfully!\nStatus: {status}", "Saved", MessageBoxButton.OK, MessageBoxImage.Information);
    }

    private void BtnDeleteNote_Click(object sender, RoutedEventArgs e)
    {
        txtNoteRemarks.Text = "";
        cbNoteCategory.SelectedIndex = 0;
        txtStatusMessage.Text = "Remarks cleared.";
    }

    private async void BtnRefreshLiveOsdHud_Click(object sender, RoutedEventArgs e)
    {
        if (_currentProfile != null && !string.IsNullOrWhiteSpace(_currentProfile.ConsumerId))
        {
            await FetchLiveOsdForHudAsync(_currentProfile.ConsumerId).ConfigureAwait(true);
        }
    }

    // =========================================================================
    // TOPBAR UTILITIES (+, 🔄, 📁, ?)
    // =========================================================================
    private void BtnImportToggle_Click(object sender, RoutedEventArgs e)
    {
        var ofd = new OpenFileDialog
        {
            Title = "Select Consumer Master Data File",
            Filter = "CSV / Text Files (*.csv;*.txt)|*.csv;*.txt|Excel Files (*.xlsx;*.xls)|*.xlsx;*.xls|All Files (*.*)|*.*"
        };
        if (ofd.ShowDialog() == true)
        {
            txtStatusMessage.Text = $"Selected consumer master file: {ofd.FileName}";
            MessageBox.Show($"File ready for indexing:\n{Path.GetFileName(ofd.FileName)}", "Consumer Master", MessageBoxButton.OK, MessageBoxImage.Information);
        }
    }

    private async void BtnReloadIndex_Click(object sender, RoutedEventArgs e)
    {
        txtStatusMessage.Text = "Scanning folders & updating image index...";
        try
        {
            await RefreshAppInfoAsync().ConfigureAwait(true);
            txtStatusMessage.Text = $"Folder status and index refreshed: {txtImageCountHeader.Text} images accessible.";
        }
        catch (Exception ex)
        {
            txtStatusMessage.Text = "Index update failed: " + ex.Message;
        }
    }

    private void BtnFolderToggle_Click(object sender, RoutedEventArgs e)
    {
        SwitchToTab(rbTabSettings);
    }

    private void BtnHelp_Click(object sender, RoutedEventArgs e)
    {
        MessageBox.Show(
            "SPOT IMAGE VIEWER — v20.56 STUDIO\n\n" +
            "KEYBOARD SHORTCUTS:\n" +
            "  • [ / ] Focus Search Bar\n" +
            "  • [ Enter ] Execute Lookup\n" +
            "  • [ ← / → ] Switch Previous / Next Spot Bill Photo\n" +
            "  • [ Esc ] Clear Search & Return to Home\n" +
            "  • [ Ctrl + B ] Toggle Sidebar Rail\n\n" +
            "NATIVE WPF DIRECTX ENGINE:\n" +
            "Runs 100% natively on Windows with sub-300ms startup and zero browser overhead.",
            "SpotImageViewer Studio Help",
            MessageBoxButton.OK,
            MessageBoxImage.Information);
    }

    private void BadgeFolderStatus_MouseDown(object sender, MouseButtonEventArgs e)
    {
        SwitchToTab(rbTabSettings);
    }

    // =========================================================================
    // TAB 2: TARIFF & THEFT CALCULATOR
    // =========================================================================
    private void BtnExecuteCalc_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            string category = cbTariffCategory.SelectedItem?.ToString() ?? "Domestic (Rural) - Rate A(DM-R)";
            string cycle = (cbBillingCycle.SelectedItem as ComboBoxItem)?.Content?.ToString() ?? "Quarterly";
            int days = int.TryParse(txtCalcDays.Text, out var d) ? d : 90;
            double units = double.TryParse(txtCalcUnits.Text, out var u) ? u : 150;
            double load = double.TryParse(txtCalcLoad.Text, out var l) ? l : 1.0;
            int provDays = int.TryParse(txtTheftProvDays.Text, out var pd) ? pd : 365;
            int provHours = int.TryParse(txtTheftProvHours.Text, out var ph) ? ph : 24;

            // 1. Regular bill calculation
            var bill = BillingEngine.CalculateBill(new BillCalcPayload
            {
                Category = category,
                Cycle = cycle,
                Days = days,
                Units = units,
                Load = load,
                LoadUnit = "kVA",
                Phase = "1",
                MeterRentApplicable = true
            });

            // 2. Dual theft calculation
            var theft = BillingEngine.CalculateTheftDual(new TheftDualPayload
            {
                Category = category,
                ConsumerType = "Consumer",
                Load = load,
                LoadUnit = "kVA",
                DaysProv = provDays,
                DaysFinal = provDays,
                ProvHours = provHours,
                FinalHours = 19
            });

            // Display Results
            txtResAssessedUnits.Text = $"{theft.prov.AssessedUnits:N0} Units";
            txtResEnergyCharge.Text = $"₹{bill.EnergyCharge:N2}";
            txtResTotalPayable.Text = $"₹{bill.GrossBill:N2}";

            var sb = new StringBuilder();
            sb.AppendLine($"⚡ STANDARD BILL: Energy Charge: ₹{bill.EnergyCharge:N2} | Fixed Charge: ₹{bill.FixedCharge:N2} | Duty: ₹{bill.EdCharge:N2}");
            sb.AppendLine($"   Gross Payable: ₹{bill.GrossBill:N2} (Rounded: ₹{bill.RoundedBill:N0})");
            sb.AppendLine();
            sb.AppendLine($"🚨 THEFT (SEC 126/135) PROVISIONAL ASSESSMENT ({provDays} days @ {provHours} hrs/day):");
            sb.AppendLine($"   Assessed Units: {theft.prov.AssessedUnits:N0} kWh");
            sb.AppendLine($"   Penal Energy Charges: ₹{theft.prov.PenalEnergyCharge:N2}");
            sb.AppendLine($"   Penal Fixed Charges: ₹{theft.prov.PenalFixedCharge:N2}");
            sb.AppendLine($"   Electricity Duty: ₹{theft.prov.ElectricityDuty:N2}");
            sb.AppendLine($"   TOTAL PROVISIONAL ASSESSMENT: ₹{theft.prov.GrossAssessment:N2}");

            txtResBreakdown.Text = sb.ToString();
            txtStatusMessage.Text = "Tariff & Theft calculation completed.";
        }
        catch (Exception ex)
        {
            MessageBox.Show("Calculation error: " + ex.Message, "Error", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    // =========================================================================
    // TAB 3: FUZZY SEARCH
    // =========================================================================
    private async void TxtFuzzyInput_KeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter)
        {
            e.Handled = true;
            await ExecuteFuzzySearchAsync().ConfigureAwait(true);
        }
    }

    private async void BtnRunFuzzySearch_Click(object sender, RoutedEventArgs e)
    {
        await ExecuteFuzzySearchAsync().ConfigureAwait(true);
    }

    private async Task ExecuteFuzzySearchAsync()
    {
        string query = txtFuzzyInput.Text?.Trim() ?? "";
        if (string.IsNullOrEmpty(query)) return;

        txtStatusMessage.Text = $"Running fuzzy search for '{query}'...";
        var sw = Stopwatch.StartNew();

        try
        {
            var results = await Database.Instance.SearchConsumerAsync(query, "name").ConfigureAwait(true);
            gridFuzzyResults.ItemsSource = results;
            sw.Stop();
            txtStatusMessage.Text = $"Found {results.Count} matches in {sw.ElapsedMilliseconds}ms";
        }
        catch (Exception ex)
        {
            txtStatusMessage.Text = "Search failed: " + ex.Message;
        }
    }

    private async void GridFuzzyResults_MouseDoubleClick(object sender, MouseButtonEventArgs e)
    {
        if (gridFuzzyResults.SelectedItem is ConsumerProfile item)
        {
            await LoadConsumerAsync(item.ConsumerId, item).ConfigureAwait(true);
        }
    }

    // =========================================================================
    // TAB 4: AUDIT STUDIO
    // =========================================================================
    private async void BtnRunAudit_Click(object sender, RoutedEventArgs e)
    {
        int maxUnits = int.TryParse(txtAuditMaxUnits.Text, out var u) ? u : 30;
        txtStatusMessage.Text = $"Loading consumers with consumption <= {maxUnits} units...";
        var sw = Stopwatch.StartNew();

        try
        {
            var results = await Database.Instance.GetLowConsumptionAuditAsync(maxUnits).ConfigureAwait(true);
            gridAuditResults.ItemsSource = results;
            sw.Stop();
            txtStatusMessage.Text = $"Loaded {results.Count} low-consumption audit records in {sw.ElapsedMilliseconds}ms";
        }
        catch (Exception ex)
        {
            txtStatusMessage.Text = "Audit query failed: " + ex.Message;
        }
    }

    private void BtnExportAuditCsv_Click(object sender, RoutedEventArgs e)
    {
        if (gridAuditResults.ItemsSource is not List<LowConsumptionItem> list || list.Count == 0)
        {
            MessageBox.Show("No audit results loaded to export.", "Info", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        var sfd = new SaveFileDialog
        {
            FileName = $"Low_Consumption_Audit_{DateTime.Now:yyyyMMdd}.csv",
            Filter = "CSV (Comma delimited) (*.csv)|*.csv"
        };
        if (sfd.ShowDialog() == true)
        {
            var sb = new StringBuilder();
            sb.AppendLine("ConsumerId,Name,Units,Category,MeterNo");
            foreach (var r in list)
            {
                sb.AppendLine($"\"{r.ConsumerId}\",\"{r.Name}\",{r.Units},\"{r.Category}\",\"{r.MeterNo}\"");
            }
            File.WriteAllText(sfd.FileName, sb.ToString(), Encoding.UTF8);
            txtStatusMessage.Text = $"Exported {list.Count} records to {sfd.FileName}";
            MessageBox.Show($"Exported {list.Count} records successfully!", "Export Done", MessageBoxButton.OK, MessageBoxImage.Information);
        }
    }

    private async void GridAuditResults_MouseDoubleClick(object sender, MouseButtonEventArgs e)
    {
        if (gridAuditResults.SelectedItem is LowConsumptionItem r)
        {
            await LoadConsumerAsync(r.ConsumerId, null).ConfigureAwait(true);
        }
    }

    // =========================================================================
    // TAB 5: LIVE OSD PORTAL
    // =========================================================================
    private async void BtnFetchLiveOsd_Click(object sender, RoutedEventArgs e)
    {
        string cid = txtLiveOsdCidInput.Text.Trim();
        if (string.IsNullOrEmpty(cid)) return;

        txtStatusMessage.Text = $"Querying WBSEDCL SAP WebDynpro Portal for {cid}...";
        panelOsdResultContent.Children.Clear();
        panelOsdResultContent.Children.Add(new TextBlock
        {
            Text = "Connecting to WBSEDCL SAP Portal...",
            Foreground = (Brush)FindResource("BrushTextSecondary"),
            FontSize = 12
        });

        try
        {
            var res = await LiveOsdService.Instance.FetchLiveOsdAsync(cid).ConfigureAwait(true);
            panelOsdResultContent.Children.Clear();

            var headerText = new TextBlock
            {
                Text = $"SAP Portal Result for Consumer: {cid}",
                FontSize = 14,
                FontWeight = FontWeights.Bold,
                Foreground = (Brush)FindResource("BrushAccentSky"),
                Margin = new Thickness(0, 0, 0, 12)
            };
            panelOsdResultContent.Children.Add(headerText);

            var spDetails = new StackPanel();
            spDetails.Children.Add(CreateOsdRow("Connection Status:", res.ConnectionStatus, res.ConnectionStatus == "Active" ? "BrushAccentEmerald" : "BrushAccentRose"));
            spDetails.Children.Add(CreateOsdRow("Total Outstanding Dues:", $"₹ {res.TotalDues:N2}", "BrushAccentAmber"));
            spDetails.Children.Add(CreateOsdRow("Unpaid Energy Bills:", $"₹ {res.Osd:N2}", "BrushTextPrimary"));
            spDetails.Children.Add(CreateOsdRow("LPSC Dues:", $"₹ {res.Lpsc:N2}", "BrushTextPrimary"));
            spDetails.Children.Add(CreateOsdRow("CCC / Office:", res.Office, "BrushTextSecondary"));
            spDetails.Children.Add(CreateOsdRow("Document / Bill Type:", res.DocType, "BrushTextSecondary"));
            spDetails.Children.Add(CreateOsdRow("Connection Date:", res.ConnDate, "BrushTextSecondary"));

            panelOsdResultContent.Children.Add(spDetails);
            txtStatusMessage.Text = $"Live OSD: {cid} Total Dues ₹{res.TotalDues:N2} ({res.ConnectionStatus})";
        }
        catch (Exception ex)
        {
            panelOsdResultContent.Children.Clear();
            panelOsdResultContent.Children.Add(new TextBlock
            {
                Text = "Error communicating with SAP Portal: " + ex.Message,
                Foreground = (Brush)FindResource("BrushAccentRose"),
                FontSize = 12
            });
            txtStatusMessage.Text = "Live OSD query failed: " + ex.Message;
        }
    }

    private UIElement CreateOsdRow(string label, string value, string brushKey)
    {
        var grid = new Grid { Margin = new Thickness(0, 4, 0, 4) };
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(200) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });

        var lbl = new TextBlock { Text = label, FontWeight = FontWeights.SemiBold, Foreground = (Brush)FindResource("BrushTextMuted"), FontSize = 11 };
        var val = new TextBlock { Text = value, FontWeight = FontWeights.Bold, Foreground = (Brush)FindResource(brushKey), FontSize = 12 };

        Grid.SetColumn(lbl, 0);
        Grid.SetColumn(val, 1);
        grid.Children.Add(lbl);
        grid.Children.Add(val);
        return grid;
    }

    // =========================================================================
    // TAB 6: SETTINGS & FOLDERS
    // =========================================================================
    private void RenderSettingsFolders(List<FolderItem> folders)
    {
        panelSettingsFoldersList.Children.Clear();
        foreach (var f in folders)
        {
            var b = new Border
            {
                Background = (Brush)FindResource("BrushSurface1"),
                BorderBrush = (Brush)FindResource("BrushBorder"),
                BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(6),
                Padding = new Thickness(12, 8, 12, 8),
                Margin = new Thickness(0, 0, 0, 6)
            };

            var sp = new StackPanel();
            var topRow = new Grid();
            topRow.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            topRow.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

            var nameText = new TextBlock { Text = f.Path, FontWeight = FontWeights.SemiBold, Foreground = (Brush)FindResource("BrushTextPrimary"), FontSize = 11.5 };
            var statusBadge = new Border
            {
                Background = f.Accessible ? (Brush)new BrushConverter().ConvertFrom("#1835c98a")! : (Brush)new BrushConverter().ConvertFrom("#18ff5f70")!,
                CornerRadius = new CornerRadius(4),
                Padding = new Thickness(6, 2, 6, 2)
            };
            statusBadge.Child = new TextBlock
            {
                Text = f.Accessible ? "ONLINE" : "OFFLINE",
                FontSize = 9.5,
                FontWeight = FontWeights.Bold,
                Foreground = f.Accessible ? (Brush)FindResource("BrushAccentEmerald") : (Brush)FindResource("BrushAccentRose")
            };

            Grid.SetColumn(nameText, 0);
            Grid.SetColumn(statusBadge, 1);
            topRow.Children.Add(nameText);
            topRow.Children.Add(statusBadge);

            var metaText = new TextBlock
            {
                Text = $"{f.ImageCount:N0} spot bill images indexed",
                FontSize = 10,
                Foreground = (Brush)FindResource("BrushTextMuted"),
                Margin = new Thickness(0, 4, 0, 0)
            };

            sp.Children.Add(topRow);
            sp.Children.Add(metaText);
            b.Child = sp;
            panelSettingsFoldersList.Children.Add(b);
        }
    }

    private async void BtnAddFolder_Click(object sender, RoutedEventArgs e)
    {
        var fbd = new OpenFolderDialog
        {
            Title = "Select Image Directory to Index"
        };
        if (fbd.ShowDialog() == true)
        {
            txtStatusMessage.Text = $"Adding folder: {fbd.FolderName}...";
            try
            {
                await Database.Instance.AddFolderAsync(fbd.FolderName).ConfigureAwait(true);
                await RefreshAppInfoAsync().ConfigureAwait(true);
                MessageBox.Show($"Added image directory:\n{fbd.FolderName}\nRe-indexing initiated.", "Folder Added", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show("Failed to add folder: " + ex.Message, "Error", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }
    }

    private async void BtnRefreshFolders_Click(object sender, RoutedEventArgs e)
    {
        txtStatusMessage.Text = "Re-checking directories...";
        await RefreshAppInfoAsync().ConfigureAwait(true);
        txtStatusMessage.Text = "Folder status refreshed.";
    }
}
