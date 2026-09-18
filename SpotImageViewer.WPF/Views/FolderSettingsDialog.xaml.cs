using System;
using System.Collections.ObjectModel;
using System.Threading.Tasks;
using System.Windows;
using SpotImageViewer.WPF.Core;

namespace SpotImageViewer.WPF.Views;

public partial class FolderSettingsDialog : Window
{
    private readonly Func<Task> _onFolderListChanged;

    public FolderSettingsDialog(ObservableCollection<FolderItem> folders, Func<Task> onFolderListChanged)
    {
        InitializeComponent();
        FoldersList.ItemsSource = folders;
        _onFolderListChanged = onFolderListChanged;
    }

    private async void OnAddFolderClick(object sender, RoutedEventArgs e)
    {
        var dialog = new Microsoft.Win32.OpenFolderDialog
        {
            Title = "Select Spot Bill Image Folder to Register",
            Multiselect = false
        };

        if (dialog.ShowDialog() == true)
        {
            string selectedPath = dialog.FolderName;
            if (!string.IsNullOrWhiteSpace(selectedPath))
            {
                var (ok, msg) = await Database.Instance.AddAdditionalFolderAsync(selectedPath);
                if (ok)
                {
                    await _onFolderListChanged();
                }
                else
                {
                    MessageBox.Show(msg, "Add Folder", MessageBoxButton.OK, MessageBoxImage.Warning);
                }
            }
        }
    }

    private async void OnRefreshClick(object sender, RoutedEventArgs e)
    {
        await _onFolderListChanged();
    }

    private void OnCloseClick(object sender, RoutedEventArgs e)
    {
        Close();
    }
}
