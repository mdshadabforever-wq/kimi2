import os
import datetime
from fpdf import FPDF
from typing import Dict, Any, List

class IIISReportPDF(FPDF):
    def __init__(self, title_text: str, subtitle_text: str = ""):
        super().__init__()
        self.title_text = title_text
        self.subtitle_text = subtitle_text
        self.alias_nb_pages()

    def header(self):
        # Slate 800 background brand bar
        self.set_fill_color(15, 23, 42)
        self.rect(0, 0, 210, 24, 'F')
        
        self.set_y(5)
        self.set_font('Helvetica', 'B', 12)
        self.set_text_color(255, 255, 255)
        self.cell(0, 6, "IIIS FOUNDER INTELLIGENCE OPERATING SYSTEM", border=0, ln=1, align='L')
        
        self.set_font('Helvetica', '', 10)
        self.cell(0, 4, f"{self.title_text} | {self.subtitle_text}", border=0, ln=1, align='L')
        
        # Reset colors for document content
        self.set_text_color(30, 41, 59)
        self.ln(12)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(100, 116, 139)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}} | Confidential - Founder Eyes Only | Generated {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", 0, 0, 'C')

    def add_section_header(self, text: str):
        self.ln(3)
        self.set_font('Helvetica', 'B', 11)
        self.set_text_color(29, 78, 216) # Deep Blue Accent
        self.cell(0, 6, text, border=0, ln=1, align='L')
        self.line(self.get_x(), self.get_y(), self.get_x() + 190, self.get_y())
        self.set_text_color(30, 41, 59) # Restore slate text
        self.ln(2)

    def add_kpis(self, kpis_list: List[tuple]):
        self.set_font('Helvetica', 'B', 8)
        self.set_fill_color(241, 245, 249) # Slate 100 background
        
        col_width = 190.0 / len(kpis_list)
        # Draw labels
        for label, val in kpis_list:
            self.cell(col_width, 6, str(label), border=1, fill=True, align='C')
        self.ln()
        # Draw values
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(15, 23, 42)
        for label, val in kpis_list:
            self.cell(col_width, 8, str(val), border=1, align='C')
        self.ln(4)
        self.set_text_color(30, 41, 59)

class PDFReportGenerator:
    """Generates Daily, Weekly, Monthly, and Annual PDFs on the fly."""
    
    @staticmethod
    def generate_daily(date_str: str, data: Dict[str, Any]) -> bytes:
        pdf = IIISReportPDF("DAILY INTELLIGENCE REPORT", f"Session: {date_str}")
        pdf.add_page()
        
        kpi_dict = data.get("kpis", {})
        total_trades = data.get("closed_trades_count", 0) + data.get("open_trades_count", 0)
        kpis = [
            ("Regime", data.get("regime", "N/A")),
            ("GEIE", data.get("geie_sentiment", "N/A")),
            ("Watchlist", str(kpi_dict.get("watchlist_count", 50))),
            ("Trades", str(total_trades)),
            ("Win Rate", f"{data.get('win_rate', 0.0):.1f}%"),
            ("Net Yield", f"{data.get('total_r', 0.0):+.2f}R")
        ]
        pdf.add_kpis(kpis)
        
        # 2. Today's Story Narrative
        pdf.add_section_header("TODAY'S STORY")
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(0, 5, data.get("narrative", "No narrative generated for this day."))
        pdf.ln(2)
        
        # 3. Trades Summary Table
        pdf.add_section_header("TRADES RECORD")
        trades = data.get("trades", [])
        if trades:
            # Header
            pdf.set_font('Helvetica', 'B', 9)
            pdf.set_fill_color(241, 245, 249)
            pdf.cell(30, 6, "Symbol", border=1, fill=True)
            pdf.cell(20, 6, "Direction", border=1, fill=True)
            pdf.cell(20, 6, "Score", border=1, fill=True)
            pdf.cell(30, 6, "Entry / Exit", border=1, fill=True)
            pdf.cell(30, 6, "Outcome", border=1, fill=True)
            pdf.cell(30, 6, "Yield", border=1, fill=True)
            pdf.cell(30, 6, "Duration", border=1, fill=True)
            pdf.ln()
            
            # Rows
            pdf.set_font('Helvetica', '', 9)
            for t in trades:
                pdf.cell(30, 6, str(t.get("symbol")), border=1)
                pdf.cell(20, 6, str(t.get("direction")), border=1)
                pdf.cell(20, 6, f"{t.get('score', 86.0):.1f}", border=1)
                pdf.cell(30, 6, f"{t.get('entry_price', 0.0):.1f} / {t.get('exit_price', 0.0):.1f}", border=1)
                pdf.cell(30, 6, str(t.get("outcome")), border=1)
                pdf.cell(30, 6, f"{t.get('r_multiple', 0.0):+.2f}R", border=1)
                pdf.cell(30, 6, f"{t.get('duration_mins', 0)} mins", border=1)
                pdf.ln()
        else:
            pdf.set_font('Helvetica', 'I', 10)
            pdf.cell(0, 6, "No trades executed during this session.", border=0, ln=1)
            pdf.ln(2)
            
        # 4. Chronological Timeline
        pdf.add_section_header("CHRONOLOGICAL SESSION TIMELINE")
        timeline = data.get("timeline", [])
        if timeline:
            pdf.set_font('Helvetica', '', 9)
            for event in timeline:
                time_str = event.get("time", "")
                title_str = event.get("title", "")
                desc_str = event.get("description", "")
                pdf.set_font('Helvetica', 'B', 9)
                pdf.cell(25, 5, time_str, border=0)
                pdf.set_font('Helvetica', 'B', 9)
                pdf.cell(60, 5, title_str, border=0)
                pdf.set_font('Helvetica', '', 9)
                pdf.cell(0, 5, desc_str, border=0, ln=1)
        else:
            pdf.set_font('Helvetica', 'I', 10)
            pdf.cell(0, 6, "No key events logged in this session.", border=0, ln=1)
            
        return bytes(pdf.output())

    @staticmethod
    def generate_weekly(week_str: str, data: Dict[str, Any]) -> bytes:
        pdf = IIISReportPDF("WEEKLY INTELLIGENCE REPORT", f"Period: {week_str}")
        pdf.add_page()
        
        # KPIs
        kpis = [
            ("Total Trades", str(data.get("total_trades", 0))),
            ("Win Rate", f"{data.get('win_rate', 0.0):.1f}%"),
            ("Net Yield", f"{data.get('total_r', 0.0):+.2f}R"),
            ("Best Day", data.get("best_day", "N/A")),
            ("Worst Day", data.get("worst_day", "N/A"))
        ]
        pdf.add_kpis(kpis)
        
        # Market Summary
        pdf.add_section_header("MARKET OVERVIEW & REGIME DYNAMICS")
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(0, 5, data.get("market_summary", "No market summary available for this week."))
        pdf.ln(2)
        
        # Sector Performance
        pdf.add_section_header("SECTOR PARTICIPATION & CONFLUENCES")
        sectors = data.get("sector_performance", {})
        if sectors:
            pdf.set_font('Helvetica', 'B', 9)
            pdf.set_fill_color(241, 245, 249)
            pdf.cell(60, 6, "Sector", border=1, fill=True)
            pdf.cell(40, 6, "Trades", border=1, fill=True)
            pdf.cell(40, 6, "Win Rate", border=1, fill=True)
            pdf.cell(50, 6, "Total Yield", border=1, fill=True)
            pdf.ln()
            
            pdf.set_font('Helvetica', '', 9)
            for sector_name, s in sectors.items():
                pdf.cell(60, 6, sector_name, border=1)
                pdf.cell(40, 6, str(s.get("trades", 0)), border=1)
                pdf.cell(40, 6, f"{s.get('win_rate', 0.0):.1f}%", border=1)
                pdf.cell(50, 6, f"{s.get('total_r', 0.0):+.2f}R", border=1)
                pdf.ln()
        else:
            pdf.set_font('Helvetica', 'I', 10)
            pdf.cell(0, 6, "No sector metrics compiled for this period.", border=0, ln=1)
            pdf.ln(2)

        # AI Lessons
        pdf.add_section_header("AI STRATEGIC INSIGHTS & LESSONS")
        pdf.set_font('Helvetica', '', 10)
        lessons = data.get("lessons", {})
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(0, 5, "What Worked:", border=0, ln=1)
        pdf.set_font('Helvetica', '', 9)
        pdf.multi_cell(0, 5, lessons.get("worked", "N/A"))
        pdf.ln(1)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(0, 5, "What Failed:", border=0, ln=1)
        pdf.set_font('Helvetica', '', 9)
        pdf.multi_cell(0, 5, lessons.get("failed", "N/A"))
        pdf.ln(1)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(0, 5, "What Repeated:", border=0, ln=1)
        pdf.set_font('Helvetica', '', 9)
        pdf.multi_cell(0, 5, lessons.get("repeated", "N/A"))
        pdf.ln(2)
        
        # Next Week Focus
        pdf.add_section_header("NEXT WEEK STRATEGIC FOCUS AREAS")
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(0, 5, data.get("next_week_focus", "Continue auditing active trends and core sectors."))
        
        return bytes(pdf.output())

    @staticmethod
    def generate_monthly(month_str: str, data: Dict[str, Any]) -> bytes:
        pdf = IIISReportPDF("MONTHLY INTELLIGENCE REPORT", f"Period: {month_str}")
        pdf.add_page()
        
        # KPIs
        kpis = [
            ("Total Trades", str(data.get("total_trades", 0))),
            ("Win Rate", f"{data.get('win_rate', 0.0):.1f}%"),
            ("Net Yield", f"{data.get('total_r', 0.0):+.2f}R"),
            ("Avg Duration", f"{data.get('avg_duration', 0.0):.1f} mins"),
            ("Avg Yield", f"{data.get('avg_r', 0.0):+.2f}R")
        ]
        pdf.add_kpis(kpis)
        
        # Sector Stats
        pdf.add_section_header("SECTOR PERFORMANCE HIGHLIGHTS")
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(50, 6, "Best Performing Sector:", border=0)
        pdf.set_font('Helvetica', '', 9)
        pdf.cell(0, 6, data.get("best_sector", "N/A"), border=0, ln=1)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(50, 6, "Worst Performing Sector:", border=0)
        pdf.set_font('Helvetica', '', 9)
        pdf.cell(0, 6, data.get("worst_sector", "N/A"), border=0, ln=1)
        pdf.ln(2)

        # Setup Stats
        pdf.add_section_header("STRATEGY & SETUP EFFECTIVENESS")
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(50, 6, "Best Setup configuration:", border=0)
        pdf.set_font('Helvetica', '', 9)
        pdf.cell(0, 6, data.get("best_setup", "N/A"), border=0, ln=1)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(50, 6, "Worst Setup configuration:", border=0)
        pdf.set_font('Helvetica', '', 9)
        pdf.cell(0, 6, data.get("worst_setup", "N/A"), border=0, ln=1)
        pdf.ln(2)

        # Founder Notes Summary
        pdf.add_section_header("FOUNDER BEHAVIORAL AUDIT SUMMARY")
        pdf.set_font('Helvetica', '', 10)
        notes_summary = data.get("founder_behavior", {})
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(0, 5, "Common Observations:", border=0, ln=1)
        pdf.set_font('Helvetica', '', 9)
        pdf.multi_cell(0, 5, notes_summary.get("observations", "N/A"))
        pdf.ln(1)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(0, 5, "Repeated Strengths:", border=0, ln=1)
        pdf.set_font('Helvetica', '', 9)
        pdf.multi_cell(0, 5, notes_summary.get("strengths", "N/A"))
        pdf.ln(1)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(0, 5, "Repeated Mistakes:", border=0, ln=1)
        pdf.set_font('Helvetica', '', 9)
        pdf.multi_cell(0, 5, notes_summary.get("mistakes", "N/A"))
        pdf.ln(2)

        # AI Conclusion
        pdf.add_section_header("AI STRATEGIC CONCLUSION")
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(0, 5, data.get("ai_conclusion", "No anomalies or major shifts detected this month."))
        
        return bytes(pdf.output())

    @staticmethod
    def generate_annual(year_str: str, data: Dict[str, Any]) -> bytes:
        pdf = IIISReportPDF("ANNUAL INTELLIGENCE REVIEW", f"Year: {year_str}")
        pdf.add_page()
        
        # KPIs
        kpis = [
            ("Total Trades", str(data.get("total_trades", 0))),
            ("Win Rate", f"{data.get('win_rate', 0.0):.1f}%"),
            ("Net Yield", f"{data.get('total_r', 0.0):+.2f}R"),
            ("Best Sector", data.get("best_sector", "N/A")),
            ("Worst Sector", data.get("worst_sector", "N/A"))
        ]
        pdf.add_kpis(kpis)

        # Setup Stats
        pdf.add_section_header("ANNUAL STRATEGY EFFECTIVENESS")
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(50, 6, "Best Setup Configuration:", border=0)
        pdf.set_font('Helvetica', '', 9)
        pdf.cell(0, 6, data.get("best_setup", "N/A"), border=0, ln=1)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(50, 6, "Worst Setup Configuration:", border=0)
        pdf.set_font('Helvetica', '', 9)
        pdf.cell(0, 6, data.get("worst_setup", "N/A"), border=0, ln=1)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(50, 6, "Largest Single Winner:", border=0)
        pdf.set_font('Helvetica', '', 9)
        pdf.cell(0, 6, data.get("largest_winner", "N/A"), border=0, ln=1)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(50, 6, "Largest Single Loser:", border=0)
        pdf.set_font('Helvetica', '', 9)
        pdf.cell(0, 6, data.get("largest_loser", "N/A"), border=0, ln=1)
        pdf.ln(2)

        # Quarter comparison
        pdf.add_section_header("QUARTERLY YIELD DISTRIBUTION")
        quarters = data.get("quarters", {})
        if quarters:
            pdf.set_font('Helvetica', 'B', 9)
            pdf.set_fill_color(241, 245, 249)
            pdf.cell(40, 6, "Quarter", border=1, fill=True)
            pdf.cell(40, 6, "Trades", border=1, fill=True)
            pdf.cell(40, 6, "Win Rate", border=1, fill=True)
            pdf.cell(70, 6, "Net Yield", border=1, fill=True)
            pdf.ln()
            
            pdf.set_font('Helvetica', '', 9)
            for q_name, q in quarters.items():
                pdf.cell(40, 6, q_name, border=1)
                pdf.cell(40, 6, str(q.get("trades", 0)), border=1)
                pdf.cell(40, 6, f"{q.get('win_rate', 0.0):.1f}%", border=1)
                pdf.cell(70, 6, f"{q.get('total_r', 0.0):+.2f}R", border=1)
                pdf.ln()
        else:
            pdf.set_font('Helvetica', 'I', 10)
            pdf.cell(0, 6, "No quarterly statistics logged.", border=0, ln=1)
            pdf.ln(2)

        # Founder Notes Summary
        pdf.add_section_header("ANNUAL FOUNDER EVOLUTION AUDIT")
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(0, 5, data.get("founder_evolution", "Notes and observations show steady refinement in decision criteria."))
        pdf.ln(2)

        # AI Strategic Review
        pdf.add_section_header("AI STRATEGIC REVIEW & CORE RECOMMENDATIONS")
        pdf.set_font('Helvetica', '', 10)
        lessons = data.get("ai_strategic_review", {})
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(0, 5, "Biggest Lessons:", border=0, ln=1)
        pdf.set_font('Helvetica', '', 9)
        pdf.multi_cell(0, 5, lessons.get("lessons", "N/A"))
        pdf.ln(1)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(0, 5, "Biggest Mistakes:", border=0, ln=1)
        pdf.set_font('Helvetica', '', 9)
        pdf.multi_cell(0, 5, lessons.get("mistakes", "N/A"))
        pdf.ln(1)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(0, 5, "Most Valuable Setup Patterns:", border=0, ln=1)
        pdf.set_font('Helvetica', '', 9)
        pdf.multi_cell(0, 5, lessons.get("patterns", "N/A"))
        
        return bytes(pdf.output())
