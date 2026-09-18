using System.Text.Json.Serialization;

namespace SpotImageViewer.WPF.Core;

public class ConsumerProfile
{
    [JsonPropertyName("consumer_id")]
    public string ConsumerId { get; set; } = "";

    [JsonPropertyName("meter_no")]
    public string MeterNo { get; set; } = "";

    [JsonPropertyName("name")]
    public string Name { get; set; } = "";

    [JsonPropertyName("address")]
    public string Address { get; set; } = "";

    [JsonPropertyName("mobile_number")]
    public string MobileNumber { get; set; } = "";

    [JsonPropertyName("contractual_load")]
    public string ContractualLoad { get; set; } = "";

    [JsonPropertyName("class")]
    public string Class { get; set; } = "";

    [JsonPropertyName("mru")]
    public string Mru { get; set; } = "";

    [JsonPropertyName("conn_phase")]
    public int ConnPhase { get; set; } = 1;
}

public class ImageItem
{
    [JsonPropertyName("consumer_id")]
    public string ConsumerId { get; set; } = "";

    [JsonPropertyName("date_original")]
    public string DateOriginal { get; set; } = "";

    [JsonPropertyName("date_iso")]
    public string DateIso { get; set; } = "";

    [JsonPropertyName("date_formatted")]
    public string DateFormatted { get; set; } = "";

    [JsonPropertyName("mru")]
    public string Mru { get; set; } = "";

    [JsonPropertyName("filename")]
    public string Filename { get; set; } = "";

    [JsonPropertyName("dir_id")]
    public int DirId { get; set; }

    [JsonPropertyName("full_path")]
    public string FullPath { get; set; } = "";

    [JsonPropertyName("exists")]
    public bool Exists { get; set; }
}

public class FolderItem
{
    [JsonPropertyName("path")]
    public string Path { get; set; } = "";

    [JsonPropertyName("accessible")]
    public bool Accessible { get; set; }

    [JsonPropertyName("is_primary")]
    public bool IsPrimary { get; set; }

    [JsonPropertyName("image_count")]
    public long ImageCount { get; set; }
}

public class AppInfoResponse
{
    [JsonPropertyName("version")]
    public string Version { get; set; } = Config.CURRENT_VERSION;

    [JsonPropertyName("total_images")]
    public long TotalImages { get; set; }

    [JsonPropertyName("available_images")]
    public long AvailableImages { get; set; }

    [JsonPropertyName("folders")]
    public List<FolderItem> Folders { get; set; } = new();

    [JsonPropertyName("has_meter_data")]
    public bool HasMeterData { get; set; }

    [JsonPropertyName("consumer_count")]
    public long ConsumerCount { get; set; }

    [JsonPropertyName("consumer_updated_at")]
    public string ConsumerUpdatedAt { get; set; } = "";

    [JsonPropertyName("theme")]
    public string Theme { get; set; } = "dark";

    [JsonPropertyName("success")]
    public bool Success { get; set; } = true;
}

public class BillCalcPayload
{
    [JsonPropertyName("category")]
    public string Category { get; set; } = "";

    [JsonPropertyName("cycle")]
    public string Cycle { get; set; } = "Monthly";

    [JsonPropertyName("days")]
    public int Days { get; set; } = 30;

    [JsonPropertyName("units")]
    public double Units { get; set; }

    [JsonPropertyName("tod_units")]
    public TodUnitsPayload? TodUnits { get; set; }

    [JsonPropertyName("load")]
    public double Load { get; set; } = 1.0;

    [JsonPropertyName("load_unit")]
    public string LoadUnit { get; set; } = "kVA";

    [JsonPropertyName("mvca")]
    public double Mvca { get; set; } = 0.0;

    [JsonPropertyName("meter_rent_applicable")]
    public bool MeterRentApplicable { get; set; } = true;

    [JsonPropertyName("is_monsoon")]
    public bool IsMonsoon { get; set; } = false;

    [JsonPropertyName("phase")]
    public string Phase { get; set; } = "1";
}

public class TodUnitsPayload
{
    [JsonPropertyName("normal")]
    public double Normal { get; set; }

    [JsonPropertyName("peak")]
    public double Peak { get; set; }

    [JsonPropertyName("off_peak")]
    public double OffPeak { get; set; }
}

public class BillCalcResult
{
    [JsonPropertyName("energy_charge")]
    public double EnergyCharge { get; set; }

    [JsonPropertyName("fixed_charge")]
    public double FixedCharge { get; set; }

    [JsonPropertyName("minimum_charge")]
    public double MinimumCharge { get; set; }

    [JsonPropertyName("min_charge_override")]
    public bool MinChargeOverride { get; set; }

    [JsonPropertyName("meter_rent")]
    public double MeterRent { get; set; }

    [JsonPropertyName("mvca_charge")]
    public double MvcaCharge { get; set; }

    [JsonPropertyName("ed_percentage")]
    public double EdPercentage { get; set; }

    [JsonPropertyName("ed_charge")]
    public double EdCharge { get; set; }

    [JsonPropertyName("gov_relief")]
    public double GovRelief { get; set; }

    [JsonPropertyName("gross_bill")]
    public double GrossBill { get; set; }

    [JsonPropertyName("rebate_timely")]
    public double RebateTimely { get; set; }

    [JsonPropertyName("rebate_epay")]
    public double RebateEpay { get; set; }

    [JsonPropertyName("rebate_special")]
    public double RebateSpecial { get; set; }

    [JsonPropertyName("rounded_bill")]
    public long RoundedBill { get; set; }

    [JsonPropertyName("months_multiplier")]
    public double MonthsMultiplier { get; set; } = 1.0;
}

public class TheftDualPayload
{
    [JsonPropertyName("category")]
    public string Category { get; set; } = "Rate A(DM-R)";

    [JsonPropertyName("consumer_type")]
    public string ConsumerType { get; set; } = "Consumer";

    [JsonPropertyName("load")]
    public double Load { get; set; } = 1.0;

    [JsonPropertyName("load_unit")]
    public string LoadUnit { get; set; } = "kVA";

    [JsonPropertyName("days_prov")]
    public int DaysProv { get; set; } = 365;

    [JsonPropertyName("days_final")]
    public int DaysFinal { get; set; } = 365;

    [JsonPropertyName("prov_hours")]
    public double ProvHours { get; set; } = 24.0;

    [JsonPropertyName("final_hours")]
    public double FinalHours { get; set; } = 19.0;

    [JsonPropertyName("adj_energy")]
    public double AdjEnergy { get; set; } = 0.0;

    [JsonPropertyName("adj_fixed")]
    public double AdjFixed { get; set; } = 0.0;

    [JsonPropertyName("adj_ed")]
    public double AdjEd { get; set; } = 0.0;
}

public class TheftResult
{
    [JsonPropertyName("assessed_units")]
    public long AssessedUnits { get; set; }

    [JsonPropertyName("penal_energy_charge")]
    public double PenalEnergyCharge { get; set; }

    [JsonPropertyName("penal_fixed_charge")]
    public double PenalFixedCharge { get; set; }

    [JsonPropertyName("electricity_duty")]
    public double ElectricityDuty { get; set; }

    [JsonPropertyName("gross_assessment")]
    public double GrossAssessment { get; set; }

    [JsonPropertyName("total_adjustments")]
    public double TotalAdjustments { get; set; }

    [JsonPropertyName("net_assessment")]
    public double NetAssessment { get; set; }

    [JsonPropertyName("breakdown")]
    public Dictionary<string, object> Breakdown { get; set; } = new();
}

public class ReverseLoadPayload
{
    [JsonPropertyName("category")]
    public string Category { get; set; } = "Rate A(DM-R)";

    [JsonPropertyName("consumer_type")]
    public string ConsumerType { get; set; } = "Consumer";

    [JsonPropertyName("target_bill")]
    public double TargetBill { get; set; }

    [JsonPropertyName("days")]
    public int Days { get; set; } = 365;

    [JsonPropertyName("hours")]
    public double Hours { get; set; } = 24.0;
}

public class LiveOsdRecord
{
    [JsonPropertyName("consumerId")]
    public string ConsumerId { get; set; } = "";

    [JsonPropertyName("name")]
    public string Name { get; set; } = "";

    [JsonPropertyName("address")]
    public string Address { get; set; } = "";

    [JsonPropertyName("office")]
    public string Office { get; set; } = "";

    [JsonPropertyName("connDate")]
    public string ConnDate { get; set; } = "";

    [JsonPropertyName("docType")]
    public string DocType { get; set; } = "Outstanding Report";

    [JsonPropertyName("connectionStatus")]
    public string ConnectionStatus { get; set; } = "";

    [JsonPropertyName("isLive")]
    public bool IsLive { get; set; }

    [JsonPropertyName("isDisconnected")]
    public bool IsDisconnected { get; set; }

    [JsonPropertyName("isDeemed")]
    public bool IsDeemed { get; set; }

    [JsonPropertyName("isTempDisconnected")]
    public bool IsTempDisconnected { get; set; }

    [JsonPropertyName("totalDues")]
    public double TotalDues { get; set; }

    [JsonPropertyName("osd")]
    public double Osd { get; set; }

    [JsonPropertyName("lpsc")]
    public double Lpsc { get; set; }

    [JsonPropertyName("fileSizeKb")]
    public double FileSizeKb { get; set; }

    [JsonPropertyName("cached")]
    public bool Cached { get; set; }

    [JsonPropertyName("status")]
    public string Status { get; set; } = "Success";

    [JsonPropertyName("pdfPath")]
    public string? PdfPath { get; set; }
}
