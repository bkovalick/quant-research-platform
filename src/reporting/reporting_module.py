import openpyxl
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows

class ReportingSystem:
    @classmethod
    def generate_report(cls, filename: str, results: dict):
        # with Workbook() as wb:
        wb = Workbook()
        # Remove default sheet created with new workbook
        default_sheet = wb.active
        wb.remove(default_sheet)
        if "summary" in results:
            summary_ws = wb.create_sheet(title="Summary")
            summary_rows = dataframe_to_rows(results["summary"], header=True, index=False)   
            for r_idx, row in enumerate(summary_rows, 1):
                for c_idx, value in enumerate(row, 1):
                    summary_ws.cell(row=r_idx, column=c_idx, value=value)

        if "time_series" in results:
            ts_ws = wb.create_sheet(title="Time Series")
            ts_rows = dataframe_to_rows(results["time_series"], header=True, index=False)
            for r_idx, row in enumerate(ts_rows, 1):
                for c_idx, value in enumerate(row, 1):
                    ts_ws.cell(row=r_idx, column=c_idx, value=value)

        wb.save(filename)
        wb.close()
