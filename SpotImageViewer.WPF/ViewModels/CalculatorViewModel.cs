using System;
using System.Collections.ObjectModel;
using System.Text.Json;
using System.Windows.Input;
using SpotImageViewer.WPF.Core;

namespace SpotImageViewer.WPF.ViewModels;

public class CalculatorViewModel : ViewModelBase
{
    private string _selectedCategory = "Domestic (Rural) - Rate A(DM-R)";
    private string _cycle = "Quarterly";
    private int _days = 90;
    private double _units = 250;
    private double _load = 1.0;
    private string _loadUnit = "kVA";
    private string _phase = "1";
    private bool _meterRentApplicable = true;
    private double _mvca = 0.0;
    private string _billSummary = "Enter parameters and click Calculate Bill";

    // Theft fields
    private string _theftCategory = "Domestic (Rural) - Rate A(DM-R)";
    private double _theftLoad = 1.5;
    private int _daysProv = 365;
    private int _daysFinal = 365;
    private int _provHours = 24;
    private int _finalHours = 19;
    private string _theftSummary = "Enter theft audit details and click Assess Theft";

    public CalculatorViewModel()
    {
        Categories = new ObservableCollection<string>
        {
            "Domestic (Rural) - Rate A(DM-R)",
            "Domestic (Urban) - Rate A(DM-U)",
            "Commercial - Rate A(CM)",
            "Commercial - Rate A(CM-II)",
            "Agriculture Normal - Rate C(A)",
            "Industry (Rural) - Rate B(I-R)"
        };

        Cycles = new ObservableCollection<string> { "Monthly", "Quarterly" };

        CalculateBillCommand = new RelayCommand(CalculateBill);
        CalculateTheftCommand = new RelayCommand(CalculateTheft);
    }

    public ObservableCollection<string> Categories { get; }
    public ObservableCollection<string> Cycles { get; }

    public string SelectedCategory
    {
        get => _selectedCategory;
        set => SetProperty(ref _selectedCategory, value);
    }

    public string Cycle
    {
        get => _cycle;
        set
        {
            if (SetProperty(ref _cycle, value))
            {
                Days = value == "Monthly" ? 30 : 90;
            }
        }
    }

    public int Days
    {
        get => _days;
        set => SetProperty(ref _days, value);
    }

    public double Units
    {
        get => _units;
        set => SetProperty(ref _units, value);
    }

    public double Load
    {
        get => _load;
        set => SetProperty(ref _load, value);
    }

    public string Phase
    {
        get => _phase;
        set => SetProperty(ref _phase, value);
    }

    public string BillSummary
    {
        get => _billSummary;
        set => SetProperty(ref _billSummary, value);
    }

    public string TheftCategory
    {
        get => _theftCategory;
        set => SetProperty(ref _theftCategory, value);
    }

    public double TheftLoad
    {
        get => _theftLoad;
        set => SetProperty(ref _theftLoad, value);
    }

    public int DaysProv
    {
        get => _daysProv;
        set => SetProperty(ref _daysProv, value);
    }

    public int DaysFinal
    {
        get => _daysFinal;
        set => SetProperty(ref _daysFinal, value);
    }

    public int ProvHours
    {
        get => _provHours;
        set => SetProperty(ref _provHours, value);
    }

    public int FinalHours
    {
        get => _finalHours;
        set => SetProperty(ref _finalHours, value);
    }

    public string TheftSummary
    {
        get => _theftSummary;
        set => SetProperty(ref _theftSummary, value);
    }

    public ICommand CalculateBillCommand { get; }
    public ICommand CalculateTheftCommand { get; }

    private void CalculateBill()
    {
        try
        {
            var req = new BillCalcPayload
            {
                Category = SelectedCategory,
                Cycle = Cycle,
                Days = Days,
                Units = Units,
                Load = Load,
                LoadUnit = _loadUnit,
                Mvca = _mvca,
                MeterRentApplicable = _meterRentApplicable,
                Phase = Phase
            };

            var res = BillingEngine.CalculateBill(req);
            BillSummary = $"⚡ Total Gross Bill: ₹{res.GrossBill:N2} (Rounded: ₹{res.RoundedBill:N0})\n" +
                          $"• Energy Charges: ₹{res.EnergyCharge:N2}\n" +
                          $"• Fixed Charges: ₹{res.FixedCharge:N2}\n" +
                          $"• Electricity Duty: ₹{res.EdCharge:N2}\n" +
                          $"• Meter Rent: ₹{res.MeterRent:N2}";
        }
        catch (Exception ex)
        {
            BillSummary = $"Calculation Error: {ex.Message}";
        }
    }

    private void CalculateTheft()
    {
        try
        {
            var req = new TheftDualPayload
            {
                Category = TheftCategory,
                Load = TheftLoad,
                LoadUnit = "kVA",
                DaysProv = DaysProv,
                DaysFinal = DaysFinal,
                ProvHours = ProvHours,
                FinalHours = FinalHours
            };

            var (prov, finalRes, diffRs, diffPct) = BillingEngine.CalculateTheftDual(req);
            TheftSummary = $"⚖️ THEFT ASSESSMENT SUMMARY\n\n" +
                           $"[PROVISIONAL BILL]:\n" +
                           $"• Assessed Units: {prov.AssessedUnits:N0} kWh\n" +
                           $"• Penal Energy: ₹{prov.PenalEnergyCharge:N2}\n" +
                           $"• Net Assessment: ₹{prov.NetAssessment:N2}\n\n" +
                           $"[FINAL BILL]:\n" +
                           $"• Assessed Units: {finalRes.AssessedUnits:N0} kWh\n" +
                           $"• Penal Energy: ₹{finalRes.PenalEnergyCharge:N2}\n" +
                           $"• Net Assessment: ₹{finalRes.NetAssessment:N2}\n\n" +
                           $"[DIFFERENCE]: ₹{diffRs:N2} ({diffPct:F1}%)";
        }
        catch (Exception ex)
        {
            TheftSummary = $"Theft Assessment Error: {ex.Message}";
        }
    }
}
