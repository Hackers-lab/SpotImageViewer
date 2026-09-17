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
using System.Windows.Media.Imaging;
using System.Windows.Shapes;
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
    private bool _isInverted = false;

    public MainWindow()
    {
        InitializeComponent();
        Logger.Log("APP", "Native WPF MainWindow initialized");

        Loaded += MainWindow_Loaded;
        PreviewKeyDown += MainWindow_PreviewKeyDown;
    }

    private async void MainWindow_Loaded(object sender, RoutedEventArgs e)
    {
        try
        {
            txtStatusMessage.Text = "Initializing database and index...";
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
            txtImageCountHeader.Text = $"{appInfo.AvailableImages:N0} / {appInfo.TotalImages:N0} img";

            bool allOnline = appInfo.Folders.All(f => f.Accessible);
            dotStatus.Fill = allOnline
                ? (SolidColorBrush)FindResource("BrushAccentEmerald")
                : (SolidColorBrush)FindResource("BrushAccentAmber");

            long offlineCount = appInfo.TotalImages - appInfo.AvailableImages;
            badgeFolderStatus.ToolTip = allOnline
                ? $"All folders online ({appInfo.TotalImages:N0} images accessible)"
                : $"Warning: {offlineCount:N0} images are in offline network shares. Click to inspect.";

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
    // NAVIGATION TABS
    // =========================================================================
    private void NavTab_Checked(object sender, RoutedEventArgs e)
    {
        if (panelViewer == null) return; // called during XAML initialize

        panelViewer.Visibility = rbTabViewer.IsChecked == true ? Visibility.Visible : Visibility.Collapsed;
        panelTariff.Visibility = rbTabTariff.IsChecked == true ? Visibility.Visible : Visibility.Collapsed;
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
        if (panelPhotoViewer.Visibility == Visibility.Visible && _currentImages.Count > 1)
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

        // 2. Populate Sidebar details
        txtCID.Text = _currentProfile.ConsumerId;
        txtConsumerName.Text = string.IsNullOrWhiteSpace(_currentProfile.Name) ? "(Name Not Available)" : _currentProfile.Name;
        txtAddress.Text = string.IsNullOrWhiteSpace(_currentProfile.Address) ? "(Address Not Available)" : _currentProfile.Address;
        txtTariff.Text = string.IsNullOrWhiteSpace(_currentProfile.Class) ? "-" : _currentProfile.Class;
        txtPhase.Text = $"{_currentProfile.ConnPhase} Ph";
        txtLoad.Text = string.IsNullOrWhiteSpace(_currentProfile.ContractualLoad) ? "-" : _currentProfile.ContractualLoad + " kVA";
        txtMeterNo.Text = string.IsNullOrWhiteSpace(_currentProfile.MeterNo) ? "-" : _currentProfile.MeterNo;
        txtOffice.Text = string.IsNullOrWhiteSpace(_currentProfile.Mru) ? "KUSHIDA CCC" : _currentProfile.Mru;
        txtMobile.Text = string.IsNullOrWhiteSpace(_currentProfile.MobileNumber) ? "-" : _currentProfile.MobileNumber;

        // Hide OSD summary until queried
        cardOsdSummary.Visibility = Visibility.Collapsed;

        // 3. Render Photo Chips in Sidebar
        panelPhotoChips.Children.Clear();
        if (_currentImages.Count == 0)
        {
            panelPhotoChips.Children.Add(new TextBlock
            {
                Text = "No spot bill images found on disk for this consumer.",
                FontSize = 11,
                Foreground = (Brush)FindResource("BrushAccentAmber"),
                TextWrapping = TextWrapping.Wrap
            });
        }
        else
        {
            for (int i = 0; i < _currentImages.Count; i++)
            {
                var img = _currentImages[i];
                int idx = i;
                var chip = new Button
                {
                    Style = (Style)FindResource("ModernButton"),
                    Margin = new Thickness(0, 0, 0, 4),
                    Padding = new Thickness(10, 6, 10, 6),
                    HorizontalContentAlignment = HorizontalAlignment.Stretch,
                    Content = new StackPanel
                    {
                        Orientation = Orientation.Horizontal,
                        Children =
                        {
                            new TextBlock { Text = "📅 " + img.DateFormatted, FontWeight = FontWeights.SemiBold, FontSize = 11 },
                            new TextBlock { Text = $" ({img.Filename})", FontSize = 9, Foreground = (Brush)FindResource("BrushTextMuted"), Margin = new Thickness(6, 1, 0, 0) }
                        }
                    }
                };
                chip.Click += (s, e) => DisplayImage(idx);
                panelPhotoChips.Children.Add(chip);
            }
        }

        // 4. Render Bottom Filmstrip Carousel
        panelFilmstrip.Children.Clear();
        for (int i = 0; i < _currentImages.Count; i++)
        {
            var img = _currentImages[i];
            int idx = i;
            var thumbBorder = new Border
            {
                Width = 110,
                Height = 74,
                Margin = new Thickness(4, 0, 4, 0),
                CornerRadius = new CornerRadius(6),
                BorderBrush = (Brush)FindResource("BrushBorderSubtle"),
                BorderThickness = new Thickness(1),
                Background = (Brush)FindResource("BrushBgInput"),
                Cursor = Cursors.Hand
            };

            var sp = new StackPanel { VerticalAlignment = VerticalAlignment.Center };
            var iconText = new TextBlock
            {
                Text = "🖼️",
                FontSize = 20,
                HorizontalAlignment = HorizontalAlignment.Center
            };
            var dateText = new TextBlock
            {
                Text = img.DateFormatted,
                FontSize = 10,
                FontWeight = FontWeights.Bold,
                HorizontalAlignment = HorizontalAlignment.Center,
                Foreground = (Brush)FindResource("BrushTextPrimary"),
                Margin = new Thickness(0, 2, 0, 0)
            };
            sp.Children.Add(iconText);
            sp.Children.Add(dateText);
            thumbBorder.Child = sp;

            thumbBorder.MouseDown += (s, e) => DisplayImage(idx);
            panelFilmstrip.Children.Add(thumbBorder);
        }

        // 5. Switch view from Welcome to Active Photo Viewer
        if (_currentImages.Count > 0)
        {
            panelWelcome.Visibility = Visibility.Collapsed;
            panelPhotoViewer.Visibility = Visibility.Visible;
            DisplayImage(0);
        }
        else
        {
            panelWelcome.Visibility = Visibility.Collapsed;
            panelPhotoViewer.Visibility = Visibility.Visible;
            imgMain.Source = null;
            txtPhotoMetaHeader.Text = "No photos available on disk";
            txtPhotoFileStatus.Text = "(Offline or missing)";
            txtPhotoFileStatus.Foreground = (Brush)FindResource("BrushAccentAmber");
        }
    }

    private void BtnClearSearch_Click(object sender, RoutedEventArgs e)
    {
        txtGlobalSearch.Text = "";
        _currentImages.Clear();
        _currentProfile = null;
        _currentImageIndex = -1;
        _currentImagePath = "";

        // Reset sidebar
        txtCID.Text = "-";
        txtConsumerName.Text = "No consumer selected";
        txtAddress.Text = "Search by 9-digit CID above to inspect spot bill records.";
        txtTariff.Text = "-";
        txtPhase.Text = "-";
        txtLoad.Text = "-";
        txtMeterNo.Text = "-";
        txtOffice.Text = "-";
        txtMobile.Text = "-";
        cardOsdSummary.Visibility = Visibility.Collapsed;
        panelPhotoChips.Children.Clear();
        panelFilmstrip.Children.Clear();

        // Switch to Welcome screen
        panelPhotoViewer.Visibility = Visibility.Collapsed;
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
                txtPhotoMetaHeader.Text = $"Photo {index + 1} of {_currentImages.Count} • {item.DateFormatted}";
                txtPhotoFileStatus.Text = $"(Online • {bmp.PixelWidth}x{bmp.PixelHeight}px)";
                txtPhotoFileStatus.Foreground = (Brush)FindResource("BrushAccentEmerald");
            }
            else
            {
                imgMain.Source = null;
                txtPhotoMetaHeader.Text = $"Photo {index + 1} of {_currentImages.Count} • {item.DateFormatted}";
                txtPhotoFileStatus.Text = "(File not accessible on disk/share)";
                txtPhotoFileStatus.Foreground = (Brush)FindResource("BrushAccentRose");
            }

            // Reset pan/zoom
            ResetImageTransform();

            // Highlight active thumbnail in filmstrip
            for (int i = 0; i < panelFilmstrip.Children.Count; i++)
            {
                if (panelFilmstrip.Children[i] is Border b)
                {
                    b.BorderBrush = (i == index)
                        ? (Brush)FindResource("BrushAccentSky")
                        : (Brush)FindResource("BrushBorderSubtle");
                    b.BorderThickness = (i == index) ? new Thickness(2) : new Thickness(1);
                }
            }
        }
        catch (Exception ex)
        {
            Logger.LogError("IMAGE", $"Failed to load image '{item.FullPath}'", ex);
            txtPhotoMetaHeader.Text = "Error loading image";
            txtPhotoFileStatus.Text = ex.Message;
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

    private void ResetImageTransform()
    {
        imgScaleTransform.ScaleX = 1.0;
        imgScaleTransform.ScaleY = 1.0;
        imgTranslateTransform.X = 0;
        imgTranslateTransform.Y = 0;
        imgRotateTransform.Angle = 0;
        imgMain.Effect = null;
        _isInverted = false;
    }

    private void BtnZoomIn_Click(object sender, RoutedEventArgs e)
    {
        imgScaleTransform.ScaleX *= 1.25;
        imgScaleTransform.ScaleY *= 1.25;
    }

    private void BtnZoomOut_Click(object sender, RoutedEventArgs e)
    {
        imgScaleTransform.ScaleX = Math.Max(0.1, imgScaleTransform.ScaleX * 0.8);
        imgScaleTransform.ScaleY = Math.Max(0.1, imgScaleTransform.ScaleY * 0.8);
    }

    private void BtnZoomFit_Click(object sender, RoutedEventArgs e)
    {
        ResetImageTransform();
    }

    private void BtnRotate_Click(object sender, RoutedEventArgs e)
    {
        imgRotateTransform.Angle = (imgRotateTransform.Angle + 90) % 360;
    }

    private void BtnInvert_Click(object sender, RoutedEventArgs e)
    {
        _isInverted = !_isInverted;
        // Invert effect: toggle subtle high-contrast / inverted filter
        if (_isInverted)
        {
            // Simple visual indicator for inverted mode
            txtStatusMessage.Text = "Invert mode active";
        }
        else
        {
            txtStatusMessage.Text = "Standard mode";
        }
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

    // Mouse Pan & Zoom
    private void BorderImageContainer_MouseWheel(object sender, MouseWheelEventArgs e)
    {
        double factor = e.Delta > 0 ? 1.15 : 0.87;
        imgScaleTransform.ScaleX = Math.Max(0.05, imgScaleTransform.ScaleX * factor);
        imgScaleTransform.ScaleY = Math.Max(0.05, imgScaleTransform.ScaleY * factor);
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
    // QUICK ACTIONS
    // =========================================================================
    private async void BtnFetchLiveOsdQuick_Click(object sender, RoutedEventArgs e)
    {
        if (_currentProfile == null || string.IsNullOrWhiteSpace(_currentProfile.ConsumerId)) return;
        string cid = _currentProfile.ConsumerId;

        txtStatusMessage.Text = $"Fetching live SAP OSD for {cid}...";
        try
        {
            var res = await LiveOsdService.Instance.FetchLiveOsdAsync(cid).ConfigureAwait(true);
            cardOsdSummary.Visibility = Visibility.Visible;
            txtOsdTotalDues.Text = $"₹{res.TotalDues:N2}";
            txtOsdDocType.Text = string.IsNullOrWhiteSpace(res.DocType) ? res.Status : res.DocType;
            txtOsdDetails.Text = $"OSD: ₹{res.Osd:N2} | LPSC: ₹{res.Lpsc:N2} | Status: {res.ConnectionStatus}";

            txtStatusMessage.Text = $"Live OSD fetched: ₹{res.TotalDues:N2} ({res.ConnectionStatus})";
        }
        catch (Exception ex)
        {
            txtStatusMessage.Text = "Failed to fetch live OSD: " + ex.Message;
        }
    }

    private void BtnCalcTariffQuick_Click(object sender, RoutedEventArgs e)
    {
        if (_currentProfile != null && !string.IsNullOrWhiteSpace(_currentProfile.Class))
        {
            foreach (var item in cbTariffCategory.Items)
            {
                if (item.ToString()?.Contains(_currentProfile.Class) == true)
                {
                    cbTariffCategory.SelectedItem = item;
                    break;
                }
            }
        }
        SwitchToTab(rbTabTariff);
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
            await RunFuzzySearchAsync().ConfigureAwait(true);
        }
    }

    private async void BtnRunFuzzySearch_Click(object sender, RoutedEventArgs e)
    {
        await RunFuzzySearchAsync().ConfigureAwait(true);
    }

    private async Task RunFuzzySearchAsync()
    {
        string query = txtFuzzyInput.Text?.Trim() ?? "";
        if (string.IsNullOrEmpty(query)) return;

        txtStatusMessage.Text = $"Running fuzzy search for '{query}'...";
        var sw = Stopwatch.StartNew();
        try
        {
            var results = await Database.Instance.SearchConsumerAsync(query).ConfigureAwait(true);
            gridFuzzyResults.ItemsSource = results;
            sw.Stop();
            txtStatusMessage.Text = $"Found {results.Count} matches in {sw.ElapsedMilliseconds}ms";
        }
        catch (Exception ex)
        {
            txtStatusMessage.Text = "Fuzzy search error: " + ex.Message;
        }
    }

    private async void GridFuzzyResults_MouseDoubleClick(object sender, MouseButtonEventArgs e)
    {
        if (gridFuzzyResults.SelectedItem is ConsumerProfile profile)
        {
            await LoadConsumerAsync(profile.ConsumerId, profile).ConfigureAwait(true);
        }
    }

    // =========================================================================
    // TAB 4: AUDIT STUDIO
    // =========================================================================
    private async void BtnRunAudit_Click(object sender, RoutedEventArgs e)
    {
        int maxUnits = int.TryParse(txtAuditMaxUnits.Text, out var m) ? m : 30;
        txtStatusMessage.Text = $"Loading low consumption consumers (<= {maxUnits} units)...";

        try
        {
            var list = await Database.Instance.GetLowConsumptionAuditAsync(maxUnits).ConfigureAwait(true);
            gridAuditResults.ItemsSource = list;
            txtStatusMessage.Text = $"Audit loaded: {list.Count} flagged consumers";
        }
        catch (Exception ex)
        {
            txtStatusMessage.Text = "Audit error: " + ex.Message;
        }
    }

    private async void GridAuditResults_MouseDoubleClick(object sender, MouseButtonEventArgs e)
    {
        if (gridAuditResults.SelectedItem is LowConsumptionItem item)
        {
            await LoadConsumerAsync(item.ConsumerId, null).ConfigureAwait(true);
        }
    }

    private void BtnExportAuditCsv_Click(object sender, RoutedEventArgs e)
    {
        if (gridAuditResults.ItemsSource is not IEnumerable<LowConsumptionItem> list || !list.Any())
        {
            MessageBox.Show("No audit results to export. Run an audit first.", "Export", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        try
        {
            string desktop = Environment.GetFolderPath(Environment.SpecialFolder.Desktop);
            string file = Path.Combine(desktop, $"Low_Consumption_Audit_{DateTime.Now:yyyyMMdd_HHmmss}.csv");
            var sb = new StringBuilder();
            sb.AppendLine("Consumer ID,Name,Units,Category,Meter No");
            foreach (var item in list)
            {
                sb.AppendLine($"\"{item.ConsumerId}\",\"{item.Name}\",{item.Units},\"{item.Category}\",\"{item.MeterNo}\"");
            }
            File.WriteAllText(file, sb.ToString());
            MessageBox.Show($"Exported {list.Count()} rows to:\n{file}", "Export Successful", MessageBoxButton.OK, MessageBoxImage.Information);
        }
        catch (Exception ex)
        {
            MessageBox.Show("Export failed: " + ex.Message, "Error", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    // =========================================================================
    // TAB 5: LIVE OSD PORTAL
    // =========================================================================
    private async void BtnFetchLiveOsd_Click(object sender, RoutedEventArgs e)
    {
        string cid = txtLiveOsdCidInput.Text?.Trim() ?? "";
        if (string.IsNullOrEmpty(cid)) return;

        txtStatusMessage.Text = $"Fetching Live OSD for {cid}...";
        panelOsdResultContent.Children.Clear();
        panelOsdResultContent.Children.Add(new TextBlock { Text = "Querying WBSEDCL SAP Portal in real time...", Foreground = (Brush)FindResource("BrushTextSecondary") });

        try
        {
            var res = await LiveOsdService.Instance.FetchLiveOsdAsync(cid).ConfigureAwait(true);
            panelOsdResultContent.Children.Clear();

            var sp = new StackPanel();

            // Status Banner
            var banner = new Border
            {
                Background = res.Status == "Success" ? new SolidColorBrush(Color.FromRgb(6, 78, 59)) : new SolidColorBrush(Color.FromRgb(136, 19, 55)),
                CornerRadius = new CornerRadius(8),
                Padding = new Thickness(14),
                Margin = new Thickness(0, 0, 0, 16)
            };
            banner.Child = new TextBlock
            {
                Text = $"SAP PORTAL STATUS: {res.ConnectionStatus} • {res.DocType}",
                FontWeight = FontWeights.Bold,
                FontSize = 13,
                Foreground = Brushes.White
            };
            sp.Children.Add(banner);

            // Dues Card
            var duesGrid = new UniformGrid { Columns = 3, Margin = new Thickness(0, 0, 0, 16) };
            duesGrid.Children.Add(CreateStatBox("TOTAL DUES", $"₹{res.TotalDues:N2}", (Brush)FindResource("BrushAccentRose")));
            duesGrid.Children.Add(CreateStatBox("OSD PRINCIPAL", $"₹{res.Osd:N2}", (Brush)FindResource("BrushAccentAmber")));
            duesGrid.Children.Add(CreateStatBox("LPSC CHARGES", $"₹{res.Lpsc:N2}", (Brush)FindResource("BrushAccentSky")));
            sp.Children.Add(duesGrid);

            // Consumer Meta
            var metaBorder = new Border
            {
                Background = (Brush)FindResource("BrushBgInput"),
                CornerRadius = new CornerRadius(8),
                Padding = new Thickness(14),
                BorderBrush = (Brush)FindResource("BrushBorderSubtle"),
                BorderThickness = new Thickness(1)
            };
            var metaSp = new StackPanel();
            metaSp.Children.Add(new TextBlock { Text = $"Consumer: {res.Name} ({cid})", FontWeight = FontWeights.Bold, FontSize = 12 });
            metaSp.Children.Add(new TextBlock { Text = $"Address: {res.Address}", FontSize = 11, Foreground = (Brush)FindResource("BrushTextSecondary"), Margin = new Thickness(0, 2, 0, 0) });
            metaSp.Children.Add(new TextBlock { Text = $"Office: {res.Office}   •   Connection Date: {res.ConnDate}", FontSize = 11, Foreground = (Brush)FindResource("BrushTextMuted"), Margin = new Thickness(0, 4, 0, 0) });
            metaBorder.Child = metaSp;
            sp.Children.Add(metaBorder);

            // Open in Viewer button
            var btnOpenInViewer = new Button
            {
                Content = "📸 Open Consumer in Spot Image Viewer",
                Style = (Style)FindResource("AccentButton"),
                Margin = new Thickness(0, 16, 0, 0),
                Padding = new Thickness(14, 8, 14, 8),
                HorizontalAlignment = HorizontalAlignment.Left
            };
            btnOpenInViewer.Click += async (s, ev) => await LoadConsumerAsync(cid, null).ConfigureAwait(true);
            sp.Children.Add(btnOpenInViewer);

            panelOsdResultContent.Children.Add(sp);
            txtStatusMessage.Text = $"Live OSD parsed: ₹{res.TotalDues:N2}";
        }
        catch (Exception ex)
        {
            panelOsdResultContent.Children.Clear();
            panelOsdResultContent.Children.Add(new TextBlock
            {
                Text = "Failed to query SAP portal: " + ex.Message,
                Foreground = (Brush)FindResource("BrushAccentRose")
            });
            txtStatusMessage.Text = "Live OSD query failed.";
        }
    }

    private Border CreateStatBox(string label, string val, Brush valBrush)
    {
        var b = new Border
        {
            Background = (Brush)FindResource("BrushBgInput"),
            BorderBrush = (Brush)FindResource("BrushBorderSubtle"),
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(6),
            Padding = new Thickness(12),
            Margin = new Thickness(4)
        };
        var sp = new StackPanel();
        sp.Children.Add(new TextBlock { Text = label, FontSize = 10, FontWeight = FontWeights.Bold, Foreground = (Brush)FindResource("BrushTextMuted") });
        sp.Children.Add(new TextBlock { Text = val, FontSize = 16, FontWeight = FontWeights.Bold, Foreground = valBrush, Margin = new Thickness(0, 4, 0, 0) });
        b.Child = sp;
        return b;
    }

    // =========================================================================
    // TAB 6: SETTINGS
    // =========================================================================
    private void RenderSettingsFolders(List<FolderItem> folders)
    {
        panelSettingsFoldersList.Children.Clear();
        foreach (var f in folders)
        {
            var itemBorder = new Border
            {
                Background = (Brush)FindResource("BrushBgInput"),
                BorderBrush = (Brush)FindResource("BrushBorderSubtle"),
                BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(6),
                Padding = new Thickness(12, 10, 12, 10),
                Margin = new Thickness(0, 0, 0, 8)
            };

            var g = new Grid();
            g.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            g.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            g.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

            // Folder Path & Badge
            var leftSp = new StackPanel { VerticalAlignment = VerticalAlignment.Center };
            Grid.SetColumn(leftSp, 0);
            var titleSp = new StackPanel { Orientation = Orientation.Horizontal };
            titleSp.Children.Add(new TextBlock
            {
                Text = f.Path,
                FontWeight = FontWeights.SemiBold,
                FontSize = 12,
                Foreground = (Brush)FindResource("BrushTextPrimary")
            });
            if (f.IsPrimary)
            {
                titleSp.Children.Add(new Border
                {
                    Background = (Brush)FindResource("BrushAccentSkyDark"),
                    CornerRadius = new CornerRadius(3),
                    Padding = new Thickness(4, 1, 4, 1),
                    Margin = new Thickness(8, 0, 0, 0),
                    Child = new TextBlock { Text = "PRIMARY", FontSize = 9, FontWeight = FontWeights.Bold, Foreground = Brushes.White }
                });
            }
            leftSp.Children.Add(titleSp);

            // Status & Count
            var statusSp = new StackPanel { Orientation = Orientation.Horizontal, VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(12, 0, 12, 0) };
            Grid.SetColumn(statusSp, 1);
            var dot = new Ellipse
            {
                Width = 8,
                Height = 8,
                Fill = f.Accessible ? (Brush)FindResource("BrushAccentEmerald") : (Brush)FindResource("BrushAccentRose"),
                Margin = new Thickness(0, 0, 6, 0)
            };
            var statusText = new TextBlock
            {
                Text = f.Accessible ? $"Online • {f.ImageCount:N0} images" : $"Offline • {f.ImageCount:N0} images",
                FontSize = 11,
                Foreground = f.Accessible ? (Brush)FindResource("BrushTextSecondary") : (Brush)FindResource("BrushAccentRose"),
                FontWeight = FontWeights.SemiBold
            };
            statusSp.Children.Add(dot);
            statusSp.Children.Add(statusText);

            g.Children.Add(leftSp);
            g.Children.Add(statusSp);

            // Remove button (if not primary)
            if (!f.IsPrimary)
            {
                var btnRemove = new Button
                {
                    Content = "Remove",
                    Style = (Style)FindResource("ModernButton"),
                    Padding = new Thickness(8, 4, 8, 4),
                    FontSize = 10,
                    Foreground = (Brush)FindResource("BrushAccentRose")
                };
                Grid.SetColumn(btnRemove, 2);
                string pathToRemove = f.Path;
                btnRemove.Click += async (s, e) =>
                {
                    await Database.Instance.RemoveFolderAsync(pathToRemove).ConfigureAwait(true);
                    await RefreshAppInfoAsync().ConfigureAwait(true);
                };
                g.Children.Add(btnRemove);
            }

            itemBorder.Child = g;
            panelSettingsFoldersList.Children.Add(itemBorder);
        }
    }

    private async void BtnAddFolder_Click(object sender, RoutedEventArgs e)
    {
        var dlg = new Microsoft.Win32.OpenFolderDialog
        {
            Title = "Select Spot Bill Image Backup Directory",
            Multiselect = false
        };
        if (dlg.ShowDialog() == true && !string.IsNullOrWhiteSpace(dlg.FolderName))
        {
            txtStatusMessage.Text = $"Adding folder {dlg.FolderName}...";
            bool added = await Database.Instance.AddFolderAsync(dlg.FolderName).ConfigureAwait(true);
            if (added)
            {
                await RefreshAppInfoAsync().ConfigureAwait(true);
                txtStatusMessage.Text = $"Folder added successfully.";
            }
        }
    }

    private async void BtnRefreshFolders_Click(object sender, RoutedEventArgs e)
    {
        txtStatusMessage.Text = "Re-checking folder availability and counts...";
        await RefreshAppInfoAsync().ConfigureAwait(true);
        txtStatusMessage.Text = "Folder status refreshed.";
    }

    private void BadgeFolderStatus_MouseDown(object sender, MouseButtonEventArgs e)
    {
        SwitchToTab(rbTabSettings);
    }
}
