using System;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;
using System.Windows.Media.Imaging;
using SpotImageViewer.WPF.Core;

namespace SpotImageViewer.WPF.ViewModels;

public class ViewerViewModel : ViewModelBase
{
    private ConsumerProfile? _consumer;
    private ImageItem? _selectedImage;
    private BitmapImage? _currentBitmap;
    private LiveOsdRecord? _liveOsd;
    private bool _isLiveOsdLoading;
    private bool _isLoadingImages;
    private int _rotationAngle;
    private double _zoomScale = 1.0;
    private string _statusMessage = "";

    public ViewerViewModel()
    {
        Images = new ObservableCollection<ImageItem>();

        RotateRightCommand = new RelayCommand(() => RotationAngle = (RotationAngle + 90) % 360);
        RotateLeftCommand = new RelayCommand(() => RotationAngle = (RotationAngle - 90 + 360) % 360);
        ResetZoomCommand = new RelayCommand(() =>
        {
            ZoomScale = 1.0;
            RotationAngle = 0;
        });

        NextImageCommand = new RelayCommand(SelectNextImage, () => Images.Count > 1);
        PrevImageCommand = new RelayCommand(SelectPrevImage, () => Images.Count > 1);
        FetchLiveOsdCommand = new RelayCommand(async () => await FetchLiveOsdAsync());
        OpenPdfCommand = new RelayCommand(OpenPdf);
        CopyConsumerIdCommand = new RelayCommand(() =>
        {
            if (!string.IsNullOrEmpty(Consumer?.ConsumerId))
            {
                Clipboard.SetText(Consumer.ConsumerId);
                StatusMessage = "Consumer ID copied to clipboard!";
            }
        });
    }

    public ObservableCollection<ImageItem> Images { get; }

    public bool HasConsumer => Consumer != null;

    public ConsumerProfile? Consumer
    {
        get => _consumer;
        set
        {
            if (SetProperty(ref _consumer, value))
            {
                OnPropertyChanged(nameof(HasConsumer));
            }
        }
    }

    public ImageItem? SelectedImage
    {
        get => _selectedImage;
        set
        {
            if (SetProperty(ref _selectedImage, value))
            {
                LoadSelectedImageBitmap();
            }
        }
    }

    public BitmapImage? CurrentBitmap
    {
        get => _currentBitmap;
        set => SetProperty(ref _currentBitmap, value);
    }

    public LiveOsdRecord? LiveOsd
    {
        get => _liveOsd;
        set => SetProperty(ref _liveOsd, value);
    }

    public bool IsLiveOsdLoading
    {
        get => _isLiveOsdLoading;
        set => SetProperty(ref _isLiveOsdLoading, value);
    }

    public bool IsLoadingImages
    {
        get => _isLoadingImages;
        set => SetProperty(ref _isLoadingImages, value);
    }

    public int RotationAngle
    {
        get => _rotationAngle;
        set => SetProperty(ref _rotationAngle, value);
    }

    public double ZoomScale
    {
        get => _zoomScale;
        set => SetProperty(ref _zoomScale, value);
    }

    public string StatusMessage
    {
        get => _statusMessage;
        set => SetProperty(ref _statusMessage, value);
    }

    public ICommand RotateRightCommand { get; }
    public ICommand RotateLeftCommand { get; }
    public ICommand ResetZoomCommand { get; }
    public ICommand NextImageCommand { get; }
    public ICommand PrevImageCommand { get; }
    public ICommand FetchLiveOsdCommand { get; }
    public ICommand OpenPdfCommand { get; }
    public ICommand CopyConsumerIdCommand { get; }

    public async Task LoadConsumerAsync(string query)
    {
        if (string.IsNullOrWhiteSpace(query)) return;

        IsLoadingImages = true;
        StatusMessage = "Loading consumer records...";
        RotationAngle = 0;
        ZoomScale = 1.0;

        try
        {
            var (profile, images) = await Database.Instance.GetConsumerImagesAsync(query);

            Application.Current.Dispatcher.Invoke(() =>
            {
                Images.Clear();
                Consumer = profile;
                LiveOsd = null;

                if (profile == null && images.Count == 0)
                {
                    StatusMessage = $"No records or images found for '{query}'.";
                    SelectedImage = null;
                    CurrentBitmap = null;
                    return;
                }

                foreach (var img in images)
                {
                    Images.Add(img);
                }

                if (Images.Count > 0)
                {
                    SelectedImage = Images[0];
                    StatusMessage = $"Loaded {Images.Count} photo(s) for CID {profile?.ConsumerId ?? query}";
                }
                else
                {
                    SelectedImage = null;
                    CurrentBitmap = null;
                    StatusMessage = $"Consumer {profile?.ConsumerId} found, but 0 photos accessible.";
                }
            });

            // Concurrently kick off Live OSD fetch
            if (profile != null && !string.IsNullOrEmpty(profile.ConsumerId))
            {
                _ = FetchLiveOsdAsync();
            }
        }
        catch (Exception ex)
        {
            Logger.LogError("VIEWER_VM", $"Error loading consumer {query}", ex);
            StatusMessage = $"Error: {ex.Message}";
        }
        finally
        {
            IsLoadingImages = false;
        }
    }

    private void LoadSelectedImageBitmap()
    {
        if (SelectedImage == null || string.IsNullOrEmpty(SelectedImage.FullPath))
        {
            CurrentBitmap = null;
            return;
        }

        try
        {
            CurrentBitmap = ImageHelper.LoadBitmapSafe(SelectedImage.FullPath);
        }
        catch (Exception ex)
        {
            Logger.LogError("VIEWER_VM", "Error decoding bitmap", ex);
            CurrentBitmap = null;
        }
    }

    public async Task FetchLiveOsdAsync()
    {
        if (Consumer == null || string.IsNullOrEmpty(Consumer.ConsumerId)) return;

        IsLiveOsdLoading = true;
        try
        {
            var result = await LiveOsdService.Instance.FetchLiveOsdAsync(Consumer.ConsumerId);
            Application.Current.Dispatcher.Invoke(() =>
            {
                LiveOsd = result;
            });
        }
        catch (Exception ex)
        {
            Logger.LogError("VIEWER_VM", "FetchLiveOsd error", ex);
        }
        finally
        {
            IsLiveOsdLoading = false;
        }
    }

    private void OpenPdf()
    {
        if (LiveOsd != null && !string.IsNullOrEmpty(LiveOsd.PdfPath) && System.IO.File.Exists(LiveOsd.PdfPath))
        {
            try
            {
                Process.Start(new ProcessStartInfo(LiveOsd.PdfPath) { UseShellExecute = true });
            }
            catch (Exception ex)
            {
                Logger.LogError("VIEWER_VM", "Open PDF error", ex);
            }
        }
    }

    private void SelectNextImage()
    {
        if (Images.Count <= 1 || SelectedImage == null) return;
        int idx = Images.IndexOf(SelectedImage);
        if (idx >= 0 && idx < Images.Count - 1)
        {
            SelectedImage = Images[idx + 1];
        }
        else
        {
            SelectedImage = Images[0]; // Wrap around
        }
    }

    private void SelectPrevImage()
    {
        if (Images.Count <= 1 || SelectedImage == null) return;
        int idx = Images.IndexOf(SelectedImage);
        if (idx > 0)
        {
            SelectedImage = Images[idx - 1];
        }
        else
        {
            SelectedImage = Images[Images.Count - 1]; // Wrap around
        }
    }

    public void ResetToWelcome()
    {
        Consumer = null;
        Images.Clear();
        SelectedImage = null;
        CurrentBitmap = null;
        LiveOsd = null;
        RotationAngle = 0;
        ZoomScale = 1.0;
        StatusMessage = "";
    }
}
