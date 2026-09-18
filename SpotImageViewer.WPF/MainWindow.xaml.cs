using System;
using System.Windows;
using System.Windows.Input;
using SpotImageViewer.WPF.ViewModels;
using SpotImageViewer.WPF.Views;

namespace SpotImageViewer.WPF;

public partial class MainWindow : Window
{
    private readonly MainViewModel _vm;

    public MainWindow()
    {
        InitializeComponent();
        _vm = new MainViewModel();
        DataContext = _vm;

        PreviewKeyDown += OnWindowPreviewKeyDown;
    }

    private void OnWindowPreviewKeyDown(object sender, KeyEventArgs e)
    {
        // Shortcut '/' to focus search box (unless already typing in a textbox)
        if (e.Key == Key.Oem2 && !(Keyboard.FocusedElement is System.Windows.Controls.TextBox))
        {
            GlobalSearchInput.Focus();
            GlobalSearchInput.SelectAll();
            e.Handled = true;
            return;
        }

        // Shortcut 'Esc' to reset search / welcome screen
        if (e.Key == Key.Escape)
        {
            _vm.ResetCommand.Execute(null);
            e.Handled = true;
            return;
        }

        // Shortcuts when viewing images (and not typing)
        if (!(Keyboard.FocusedElement is System.Windows.Controls.TextBox))
        {
            if (e.Key == Key.R)
            {
                _vm.ViewerVM.RotateRightCommand.Execute(null);
                e.Handled = true;
            }
            else if (e.Key == Key.Left)
            {
                _vm.ViewerVM.PrevImageCommand.Execute(null);
                e.Handled = true;
            }
            else if (e.Key == Key.Right)
            {
                _vm.ViewerVM.NextImageCommand.Execute(null);
                e.Handled = true;
            }
        }
    }

    private void OnSearchInputKeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter)
        {
            _vm.SearchCommand.Execute(null);
            e.Handled = true;
        }
    }

    private void OnTabRadioChecked(object sender, RoutedEventArgs e)
    {
        if (ViewerTabContent == null || CalculatorTabContent == null) return;

        if (TabRadioViewer.IsChecked == true)
        {
            ViewerTabContent.Visibility = Visibility.Visible;
            CalculatorTabContent.Visibility = Visibility.Collapsed;
        }
        else if (TabRadioCalc.IsChecked == true)
        {
            ViewerTabContent.Visibility = Visibility.Collapsed;
            CalculatorTabContent.Visibility = Visibility.Visible;
        }
    }

    private void OnFoldersButtonClick(object sender, RoutedEventArgs e)
    {
        var dlg = new FolderSettingsDialog(_vm.Folders, async () => await _vm.InitializeAppInfoAsync())
        {
            Owner = this
        };
        dlg.ShowDialog();
    }

    private void OnLogoMouseDown(object sender, MouseButtonEventArgs e)
    {
        _vm.ResetCommand.Execute(null);
        TabRadioViewer.IsChecked = true;
    }
}
