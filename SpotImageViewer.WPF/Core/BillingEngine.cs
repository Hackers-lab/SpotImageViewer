using System;
using System.Collections.Generic;

namespace SpotImageViewer.WPF.Core;

public static class BillingEngine
{
    public static BillCalcResult CalculateBill(BillCalcPayload p)
    {
        double multiplier = p.Cycle switch
        {
            "Quarterly" => 3.0,
            "Pro-Rata" or "Benefit" => Math.Max(0.01, p.Days / 30.0),
            _ => 1.0
        };

        double loadKva = p.LoadUnit == "HP" ? p.Load * 0.746 : p.Load;
        if (p.Category.Contains("CM") && loadKva < 1.0)
        {
            loadKva = 1.0; // Floor for commercial
        }

        double energyCharge = 0.0;
        double totalUnits = p.Units;

        // TOD calculation
        if (p.TodUnits != null && (p.TodUnits.Normal > 0 || p.TodUnits.Peak > 0 || p.TodUnits.OffPeak > 0))
        {
            totalUnits = p.TodUnits.Normal + p.TodUnits.Peak + p.TodUnits.OffPeak;
            energyCharge = (p.TodUnits.Normal * 7.12) + (p.TodUnits.Peak * 8.98) + (p.TodUnits.OffPeak * 6.30);
        }
        else
        {
            // Tiered slabs by category
            energyCharge = CalculateSlabEnergy(p.Category, totalUnits, multiplier);
        }

        // Fixed charges
        double fcRate = GetFixedChargeRate(p.Category);
        double fixedCharge = loadKva * fcRate * multiplier;
        if (p.Category.Contains("DM") && fixedCharge < (30.0 * multiplier))
        {
            fixedCharge = 30.0 * multiplier;
        }
        if (p.IsMonsoon && p.Category.Contains("Rate C"))
        {
            fixedCharge *= 0.5; // Monsoon rebate for agriculture
        }

        // Minimum charge floor
        double minFloorRate = GetMinChargeRate(p.Category);
        double minCharge = loadKva * minFloorRate * multiplier;
        bool minOverride = false;
        if ((energyCharge + fixedCharge) < minCharge && minCharge > 100.0)
        {
            energyCharge = minCharge - fixedCharge;
            minOverride = true;
        }

        // Meter rent
        double meterRent = 0.0;
        if (p.MeterRentApplicable)
        {
            double baseRent = (p.Phase == "3" ? 30.0 : 10.0);
            if (p.Category.Contains("CM")) baseRent = (p.Phase == "3" ? 50.0 : 15.0);
            meterRent = baseRent * multiplier;
        }

        // MVCA
        double mvcaCharge = totalUnits * p.Mvca;

        // Electricity Duty (ED)
        double monthlyUnits = totalUnits / multiplier;
        double edPercent = GetEdPercentage(p.Category, monthlyUnits);
        double edCharge = (energyCharge + mvcaCharge) * (edPercent / 100.0);

        // Domestic Government Relief (Hasir Alo)
        double govRelief = 0.0;
        if (p.Category.Contains("DM") && totalUnits <= (300.0 * multiplier))
        {
            govRelief = CalculateDomesticRelief(totalUnits, multiplier, p.Phase);
        }

        double grossBill = energyCharge + fixedCharge + meterRent + mvcaCharge + edCharge - govRelief;

        // Rebates
        double rebateTimely = energyCharge * 0.01;
        double rebateEpay = energyCharge * 0.01;
        double rebateSpecial = (p.TodUnits == null) ? energyCharge * 0.05 : 0.0;

        return new BillCalcResult
        {
            EnergyCharge = Math.Round(energyCharge, 2),
            FixedCharge = Math.Round(fixedCharge, 2),
            MinimumCharge = Math.Round(minCharge, 2),
            MinChargeOverride = minOverride,
            MeterRent = Math.Round(meterRent, 2),
            MvcaCharge = Math.Round(mvcaCharge, 2),
            EdPercentage = edPercent,
            EdCharge = Math.Round(edCharge, 2),
            GovRelief = Math.Round(govRelief, 2),
            GrossBill = Math.Round(grossBill, 2),
            RebateTimely = Math.Round(rebateTimely, 2),
            RebateEpay = Math.Round(rebateEpay, 2),
            RebateSpecial = Math.Round(rebateSpecial, 2),
            RoundedBill = (long)Math.Round(grossBill),
            MonthsMultiplier = multiplier
        };
    }

    private static double CalculateSlabEnergy(string category, double units, double mult)
    {
        // Domestic Rural / Urban Slabs (WBSEDCL Rate A(DM))
        if (category.Contains("DM"))
        {
            double[] limits = { 102 * mult, 180 * mult, 300 * mult, 600 * mult, 900 * mult };
            double[] rates = { 5.26, 5.86, 6.42, 7.31, 7.45, 8.84 };
            return CalculateTiered(units, limits, rates);
        }
        else if (category.Contains("CM"))
        {
            // Commercial
            double energy = units * 7.12;
            double discountUnits = Math.Min(units, 100 * mult);
            return energy - (discountUnits * 0.02);
        }
        else if (category.Contains("Rate C"))
        {
            // Agriculture
            return units * 4.05;
        }
        else if (category.Contains("Rate B"))
        {
            // Industry Rural
            return units * 6.85;
        }
        return units * 6.50;
    }

    private static double CalculateTiered(double units, double[] limits, double[] rates)
    {
        double total = 0.0;
        double prev = 0.0;
        for (int i = 0; i < limits.Length; i++)
        {
            double cap = limits[i];
            if (units > cap)
            {
                total += (cap - prev) * rates[i];
                prev = cap;
            }
            else
            {
                total += (units - prev) * rates[i];
                return total;
            }
        }
        if (units > prev)
        {
            total += (units - prev) * rates[rates.Length - 1];
        }
        return total;
    }

    private static double GetFixedChargeRate(string cat) => cat switch
    {
        _ when cat.Contains("DM") => 15.0,
        _ when cat.Contains("CM-II") => 60.0,
        _ when cat.Contains("CM") => 30.0,
        _ when cat.Contains("Rate C") => 20.0,
        _ when cat.Contains("Rate B") => 40.0,
        _ => 20.0
    };

    private static double GetMinChargeRate(string cat) => cat switch
    {
        _ when cat.Contains("CM") => 50.0,
        _ when cat.Contains("Rate B") => 75.0,
        _ => 0.0
    };

    private static double GetEdPercentage(string cat, double monthlyUnits)
    {
        if (cat.Contains("DM"))
        {
            if (monthlyUnits <= 25) return 0.0;
            if (monthlyUnits <= 60) return 5.0;
            return 10.0;
        }
        return 10.0;
    }

    private static double CalculateDomesticRelief(double units, double mult, string phase)
    {
        double relief = 0.0;
        double u1 = Math.Min(units, 34 * mult);
        relief += u1 * 0.90;

        if (units > 34 * mult)
        {
            double u2 = Math.Min(units - 34 * mult, (60 - 34) * mult);
            relief += u2 * 0.90;
        }
        if (units > 60 * mult)
        {
            double u3 = Math.Min(units - 60 * mult, (100 - 60) * mult);
            relief += u3 * 0.74;
        }
        if (units > 100 * mult)
        {
            double u4 = Math.Min(units - 100 * mult, (300 - 100) * mult);
            relief += u4 * 0.79;
        }

        if (phase == "1") relief += 10.0 * mult;
        return relief;
    }

    public static TheftResult CalculateTheftSingle(TheftDualPayload p, int days, double hours)
    {
        double loadKva = p.LoadUnit == "HP" ? p.Load * 0.746 : p.Load;
        double lf = p.Category.Contains("DM") ? 0.50 : 0.75;

        // Section 135 Assessed Units
        long assessedUnits = (long)Math.Round(loadKva * 0.85 * lf * days * hours);
        double months = days / (365.0 / 12.0);
        double unitsPerMonth = months > 0 ? assessedUnits / months : 0.0;

        double normalRate = p.ConsumerType == "Non-Consumer" ? 8.84 : 6.50;
        double normalEnergy = assessedUnits * normalRate;
        double penalEnergy = normalEnergy * 2.0;

        double fcRate = GetFixedChargeRate(p.Category);
        double roundedMonths = Math.Ceiling(months);
        double normalFc = loadKva * fcRate * roundedMonths;
        double penalFc = normalFc * 2.0;

        double edRate = 0.10;
        double edAmount = (penalEnergy + penalFc) * edRate;

        double gross = penalEnergy + penalFc + edAmount;
        double totalAdj = p.AdjEnergy + p.AdjFixed + p.AdjEd;
        double net = gross - totalAdj;

        return new TheftResult
        {
            AssessedUnits = assessedUnits,
            PenalEnergyCharge = Math.Round(penalEnergy, 2),
            PenalFixedCharge = Math.Round(penalFc, 2),
            ElectricityDuty = Math.Round(edAmount, 2),
            GrossAssessment = Math.Round(gross, 2),
            TotalAdjustments = Math.Round(totalAdj, 2),
            NetAssessment = Math.Round(net, 2),
            Breakdown = new Dictionary<string, object>
            {
                ["load_kva"] = Math.Round(loadKva, 3),
                ["lf"] = lf,
                ["days"] = days,
                ["hours"] = hours,
                ["units"] = assessedUnits,
                ["months"] = Math.Round(months, 2),
                ["penal_energy"] = Math.Round(penalEnergy, 2),
                ["penal_fc"] = Math.Round(penalFc, 2),
                ["ed_amount"] = Math.Round(edAmount, 2)
            }
        };
    }

    public static (TheftResult prov, TheftResult finalRes, double diffRs, double diffPct) CalculateTheftDual(TheftDualPayload p)
    {
        var prov = CalculateTheftSingle(p, p.DaysProv, p.ProvHours);
        var finalRes = CalculateTheftSingle(p, p.DaysFinal, p.FinalHours);

        double diffRs = Math.Round(prov.NetAssessment - finalRes.NetAssessment, 2);
        double diffPct = prov.NetAssessment > 0 ? Math.Round((diffRs / prov.NetAssessment) * 100.0, 1) : 0.0;

        return (prov, finalRes, diffRs, diffPct);
    }

    public static (double loadKva, double loadKw, double resultingGross, long assessedUnits) ReverseLoadSolver(ReverseLoadPayload p)
    {
        double low = 0.01;
        double high = 2000.0;
        double bestLoad = low;

        for (int i = 0; i < 60; i++)
        {
            double mid = (low + high) / 2.0;
            var testPayload = new TheftDualPayload
            {
                Category = p.Category,
                ConsumerType = p.ConsumerType,
                Load = mid,
                LoadUnit = "kVA",
                DaysProv = p.Days,
                ProvHours = p.Hours
            };
            var res = CalculateTheftSingle(testPayload, p.Days, p.Hours);
            if (res.GrossAssessment < p.TargetBill)
            {
                bestLoad = mid;
                low = mid;
            }
            else
            {
                high = mid;
            }
        }

        var finalPayload = new TheftDualPayload
        {
            Category = p.Category,
            ConsumerType = p.ConsumerType,
            Load = bestLoad,
            LoadUnit = "kVA",
            DaysProv = p.Days,
            ProvHours = p.Hours
        };
        var finalResult = CalculateTheftSingle(finalPayload, p.Days, p.Hours);

        return (
            Math.Round(bestLoad, 3),
            Math.Round(bestLoad * 0.85, 3),
            finalResult.GrossAssessment,
            finalResult.AssessedUnits
        );
    }
}
