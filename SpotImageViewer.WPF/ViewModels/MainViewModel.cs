using System;
using System.Collections.ObjectModel;
using System.Linq;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;
using SpotImageViewer.WPF.Core;

namespace SpotImageViewer.WPF.ViewModels;

public class MainViewModel : ViewModelBase
{
    private string _searchText = "";
    private long _totalImages;
    private long _availableImages;
    private long _consumerCount;
    private bool _hasOfflineFolders;
    private int _selectedTabIndex = 0;

    public MainViewModel()
    {
        ViewerVM = new ViewerViewModel();
        CalculatorVM = new CalculatorViewModel();
        Folders = new ObservableCollection<FolderItem>();

        SearchCommand = new RelayCommand(async () => await ExecuteSearchAsync());
        ResetCommand = new RelayCommand(() =>
        {
            SearchText = "";
            ViewerVM.ResetToWelcome();
            SelectedTabIndex = 0;
        });

        _ = InitializeAppInfoAsync();
    }

    public ViewerViewModel ViewerVM { get; }
    public CalculatorViewModel CalculatorVM { get; }
    public ObservableCollection<FolderItem> Folders { get; }

    public string SearchText
    {
        get => _searchText;
        set => SetProperty(ref _searchText, value);
    }

    public long TotalImages
    {
        get => _totalImages;
        set => SetProperty(ref _totalImages, value);
    }

    public long AvailableImages
    {
        get => _availableImages;
        set => SetProperty(ref _availableImages, value);
    }

    public long ConsumerCount
    {
        get => _consumerCount;
        set => SetProperty(ref _consumerCount, value);
    }

    public bool HasOfflineFolders
    {
        get => _hasOfflineFolders;
        set => SetProperty(ref _hasOfflineFolders, value);
    }

    public int SelectedTabIndex
    {
        get => _selectedTabIndex;
        set => SetProperty(ref _selectedTabIndex, value);
    }

    public ICommand SearchCommand { get; }
    public ICommand ResetCommand { get; }

    public async Task InitializeAppInfoAsync()
    {
        try
        {
            var info = await Database.Instance.GetAppInfoAsync();
            Application.Current.Dispatcher.Invoke(() =>
            {
                TotalImages = info.TotalImages;
                AvailableImages = info.AvailableImages;
                ConsumerCount = info.ConsumerCount;

                Folders.Clear();
                foreach (var f in info.Folders)
                {
                    Folders.Add(f);
                }

                HasOfflineFolders = Folders.Any(f => !f.Accessible);
            });
        }
        catch (Exception ex)
        {
            Logger.LogError("MAIN_VM", "InitializeAppInfo error", ex);
        }
    }

    public async Task ExecuteSearchAsync()
    {
        if (string.IsNullOrWhiteSpace(SearchText)) return;

        SelectedTabIndex = 0; // Switch to Viewer tab
        await ViewerVM.LoadConsumerAsync(SearchText.Trim());
    }
}
