import pandas as pd
import numpy as np
import logging

type IFRSData = dict[str, pd.Series | None]
type Ratio = pd.Series | float | None

class Ratios:
    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def __safe_divide(self, numerator : Ratio, denominator : Ratio) -> Ratio:
        """Safe division with handling of zero values and missing data. Returns None if division cannot be performed."""
        if denominator is None or numerator is None:
            return None
        try:
            if isinstance(denominator, pd.Series):
                result = numerator / denominator.replace(0, np.nan)
                return result
            else:
                return numerator / denominator if denominator != 0 else None
        except:
            return None

    def icr(self, data: IFRSData) -> Ratio:
        """Interest Coverage Ratio (Operating Profit / Interest Expense)"""
        operating_profit = data.get('operating_profit')
        if operating_profit is None:
            self.logger.debug("not enoung data of ICR: missing operating profit")
            return None

        interest_expense = data.get('interest_expense')
        if interest_expense is None:
            self.logger.debug("not enough data for ICR: missing interest expense")
            return None

        return self.__safe_divide(data['operating_profit'], data['interest_expense'])

    def leverage(self, data: IFRSData) -> Ratio:
        """Leverage (Total Debt / Total Equity)"""

        long_term_liabilities = data.get('long_term_liabilities')
        if long_term_liabilities is None:
            self.logger.debug("not enough data for leverage: missing long term liabilities")
            return None

        current_liabilities = data.get('current_liabilities')
        if current_liabilities is None:
            self.logger.debug("not enough data for leverage: missing current liabilities")
            return None

        total_equity = data.get('total_equity')
        if total_equity is None:
            self.logger.debug("not enough data for leverage: missing total equity")
            return None

        total_debt = long_term_liabilities.add(current_liabilities, fill_value=0)
        return self.__safe_divide(total_debt, total_equity)

    def lvgi(self, leverage: Ratio) -> Ratio:
        """Leverage ratio of the current year (t) to the prior year (t-1)"""
        if isinstance(leverage, pd.Series):
            return leverage.div(leverage.shift(1))
        else:
            self.logger.debug("failed to calculate LVGI: leverage has a wrong type")
            return None

    def tata(self, data: IFRSData) -> Ratio:
        """Total Accruals to Total Assets"""
        cfo = data.get('cfo')
        if cfo is None:
            self.logger.debug("not enough data for TATA: missing cfo")
            return None

        net_profit = data.get('net_profit')
        if net_profit is None:
            self.logger.debug("not enough data for TATA: missing net_profit")
            return None

        current_assets = data.get('current_assets')
        if current_assets is None:
            self.logger.debug("not enough data for TATA: missing current assets")
            return None

        non_current_assets = data.get('non_current_assets')
        if non_current_assets is None:
            self.logger.debug("not enough data for TATA: missing non current assets")
            return None

        total_assets = current_assets.add(
            non_current_assets, fill_value = 0
        )
        total_accruals = net_profit.sub(cfo, fill_value=0)
        return self.__safe_divide(total_accruals, total_assets)

    def current_ratio(self, data: IFRSData) -> Ratio:
        current_assets = data.get('current_assets')
        if current_assets is None:
            self.logger.debug("not enough data for Current Ratio: missing current assets")
            return None

        current_liabilities = data.get('current_liabilities')
        if current_liabilities is None:
            self.logger.debug("not enough data for Current Ratio: missing current liabilities")
            return None

        return self.__safe_divide(current_assets, current_liabilities)

    def aqi(self, data: IFRSData) -> Ratio:
        fixed_assets = data.get('fixed_assets')
        if fixed_assets is None:
            self.logger.debug("not enough data for AQI: missing fixed assets")
            return None

        current_assets = data.get('current_assets')
        if current_assets is None:
            self.logger.debug("not enough data for AQI: missing current assets")
            return None

        non_current_assets = data.get('non_current_assets')
        if non_current_assets is None:
            self.logger.debug("not enough data for AQI: missing non current assets")
            return None

        total_assets = current_assets.add(non_current_assets, fill_value=0)
        current_plus_ppe = current_assets.add(fixed_assets, fill_value=0)
        ratio = self.__safe_divide(current_plus_ppe, total_assets)
        if ratio is None:
            self.logger.debug("failed to calculate AQI: ratio has a wrong type")
            return None

        asset_quality = 1 - ratio
        if not isinstance(asset_quality, pd.Series):
            self.logger.debug("failed to calculate AQI: asset_quality has a wrong type")
            return None

        return self.__safe_divide(asset_quality.shift(1), asset_quality)

    def gmi(self, data: IFRSData) -> Ratio:
        """GMI - Gross Margin Index"""
        gross_profit = data.get('gross_profit')
        if gross_profit is None:
            self.logger.debug("not enough data for GMI: missing gross profit")
            return None

        revenue = data.get('revenue')
        if revenue is None:
            self.logger.debug("not enough data for GMI: missing revenue")
            return None

        gross_margin = self.__safe_divide(gross_profit, revenue)
        if not isinstance(gross_margin, pd.Series):
            self.logger.debug("failed to calculate GMI: gross_margin has a wrong type")
            return None

        return self.__safe_divide(gross_margin.shift(1), gross_margin)

    def sgai(self, data: IFRSData) -> Ratio:
        """SGAI - Sales, General and Administrative Expenses Index"""
        sga = data.get('sga')
        if sga is None:
            self.logger.debug("not enough data for SGAI: missing sga")
            return None

        revenue = data.get('revenue')
        if revenue is None:
            self.logger.debug("not enough data for SGAI: missing revenue")
            return None

        sga_ratio = self.__safe_divide(sga, revenue)
        if not isinstance(sga_ratio, pd.Series):
            self.logger.debug("failed to calculate SGAI: sga_ratio has a wrong type")
            return None

        return sga_ratio.div(sga_ratio.shift(1))

    def depi(self, data: IFRSData) -> Ratio:
        """DEPI - Depreciation Index"""
        depreciation = data.get('depreciation')
        if depreciation is None:
            self.logger.debug("not enough data for DEPI: missing depreciation")
            return None

        fixed_assets = data.get('fixed_assets')
        if fixed_assets is None:
            self.logger.debug("not enough data for DEPI: missing fixed assets")
            return None

        depreciation_ratio = self.__safe_divide(depreciation.shift(1), depreciation)
        ppe_ratio = self.__safe_divide(fixed_assets, fixed_assets.shift(1))
        if not isinstance(depreciation_ratio, pd.Series) or not isinstance(ppe_ratio, pd.Series):
            self.logger.debug("failed to calculate DEPI: ratios have a wrong type")
            return None

        return self.__safe_divide(depreciation_ratio, ppe_ratio)

    def dsri(self, data: IFRSData) -> Ratio:
        """DSRI - Days Sales in Receivables Index"""
        accounts_receivable = data.get('accounts_receivable')
        if accounts_receivable is None:
            self.logger.debug("not enough data for DSRI: missing accounts receivable")
            return None

        revenue = data.get('revenue')
        if revenue is None:
            self.logger.debug("not enough data for DSRI: missing revenue")
            return None

        receivables_ratio = self.__safe_divide(accounts_receivable, revenue)
        if not isinstance(receivables_ratio, pd.Series):
            return None

        return receivables_ratio.div(receivables_ratio.shift(1))

    def sgi(self, data: IFRSData) -> Ratio:
        """SGI - Sales Growth Index"""
        revenue = data.get('revenue')
        if revenue is None:
            self.logger.debug("not enough data for SGI: missing revenue")
            return None

        return self.__safe_divide(revenue, revenue.shift(1))

    def rofa(self, data: IFRSData) -> Ratio:
        """ROFA - Return on Fixed Assets"""
        net_profit = data.get('net_profit')
        if net_profit is None:
            self.logger.debug("not enough data for ROFA: missing net profit")
            return None

        fixed_assets = data.get('fixed_assets')
        if fixed_assets is None:
            self.logger.debug("not enough data for ROFA: missing fixed assets")
            return None

        return self.__safe_divide(net_profit, fixed_assets)

    def fat(self, data: IFRSData) -> Ratio:
        """FAT - Fixed Assets Turnover"""
        revenue = data.get('revenue')
        if revenue is None:
            self.logger.debug("not enough data for FAT: missing revenue")
            return None

        fixed_assets = data.get('fixed_assets')
        if fixed_assets is None:
            self.logger.debug("not enough data for FAT: missing fixed assets")
            return None

        return self.__safe_divide(revenue, fixed_assets)

    def m_score(self, dsri: Ratio, gmi: Ratio, aqi: Ratio, sgi: Ratio,
            depi: Ratio, sgai: Ratio, lvgi: Ratio, tata: Ratio) -> Ratio:
        """M-Score (Beneish M-score)"""
        if (dsri is None or gmi is None or aqi is None or sgi is None or
            depi is None or sgai is None or lvgi is None or tata is None):
            self.logger.debug("not enough data for M-Score: some components are missing")
            return None

        return (
            -4.84
            + 0.92 * dsri
            + 0.528 * gmi
            + 0.404 * aqi
            + 0.892 * sgi
            + 0.115 * depi
            - 0.172 * sgai
            + 4.679 * tata
            - 0.327 * lvgi
        )