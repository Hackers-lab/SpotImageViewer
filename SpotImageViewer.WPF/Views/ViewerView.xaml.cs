using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;

namespace SpotImageViewer.WPF.Views;

public partial class ViewerView : UserControl
{
    private Point _lastMousePosition;
    private bool _isPanning = false;

    public ViewerView()
    {
        InitializeComponent();

        CanvasContainer.MouseWheel += OnCanvasMouseWheel;
        CanvasContainer.MouseDown += OnCanvasMouseDown;
        CanvasContainer.MouseMove += OnCanvasMouseMove;
        CanvasContainer.MouseUp += OnCanvasMouseUp;
        CanvasContainer.MouseLeave += OnCanvasMouseUp;
    }

    private void OnCanvasMouseWheel(object sender, MouseWheelEventArgs e)
    {
        double zoomFactor = e.Delta > 0 ? 1.15 : 0.87;
        double newScaleX = ImgScale.ScaleX * zoomFactor;
        double newScaleY = ImgScale.ScaleY * zoomFactor;

        // Limit zoom range
        if (newScaleX < 0.2 || newScaleX > 15.0) return;

        Point mousePos = e.GetPosition(ImageTransformHost);

        // Adjust translation to zoom towards mouse cursor
        ImgTranslate.X -= (mousePos.X * (zoomFactor - 1));
        ImgTranslate.Y -= (mousePos.Y * (zoomFactor - 1));

        ImgScale.ScaleX = newScaleX;
        ImgScale.ScaleY = newScaleY;

        e.Handled = true;
    }

    private void OnCanvasMouseDown(object sender, MouseButtonEventArgs e)
    {
        if (e.ChangedButton == MouseButton.Left)
        {
            if (e.ClickCount == 2)
            {
                // Double click resets zoom and pan
                ImgScale.ScaleX = 1.0;
                ImgScale.ScaleY = 1.0;
                ImgTranslate.X = 0;
                ImgTranslate.Y = 0;
                return;
            }

            _isPanning = true;
            _lastMousePosition = e.GetPosition(CanvasContainer);
            CanvasContainer.CaptureMouse();
            Cursor = Cursors.SizeAll;
        }
    }

    private void OnCanvasMouseMove(object sender, MouseEventArgs e)
    {
        if (_isPanning)
        {
            Point currentPos = e.GetPosition(CanvasContainer);
            Vector delta = currentPos - _lastMousePosition;

            ImgTranslate.X += delta.X;
            ImgTranslate.Y += delta.Y;

            _lastMousePosition = currentPos;
        }
    }

    private void OnCanvasMouseUp(object sender, MouseEventArgs e)
    {
        if (_isPanning)
        {
            _isPanning = false;
            CanvasContainer.ReleaseMouseCapture();
            Cursor = Cursors.Arrow;
        }
    }
}
