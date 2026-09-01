import sys
import csv
import numpy as np
import pandas as pd
from scipy import stats

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QDoubleSpinBox, QGroupBox, QFrame, QSplitter,
    QScrollArea, QPushButton, QFileDialog, QMessageBox, QSpinBox, QProgressBar
)
from PyQt5.QtCore import Qt

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# -------------------------------------------------------------------------
# UI Styling (Dark Precision Instrumentation Theme)
# -------------------------------------------------------------------------
DARK_STYLE = """
QMainWindow {
    background-color: #090D11;
}
QWidget {
    color: #C9D1D9;
    font-family: "Segoe UI", "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 11px;
}
QGroupBox {
    border: 1px solid #1F2937;
    border-radius: 6px;
    margin-top: 10px;
    font-weight: bold;
    color: #38BDF8;
    background-color: #111827;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 8px;
    background-color: #111827;
    border-radius: 3px;
}
QLabel {
    color: #9CA3AF;
}
QDoubleSpinBox, QSpinBox {
    background-color: #090D11;
    border: 1px solid #374151;
    border-radius: 4px;
    padding: 4px 6px;
    color: #38BDF8;
    font-weight: bold;
}
QDoubleSpinBox:focus, QSpinBox:focus {
    border: 1px solid #38BDF8;
}
QPushButton {
    background-color: #1F2937;
    color: #38BDF8;
    border: 1px solid #374151;
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #374151;
    border-color: #38BDF8;
}
QPushButton:pressed {
    background-color: #0284C7;
    color: #FFFFFF;
}
QFrame#metricCard {
    background-color: #090D11;
    border: 1px solid #1F2937;
    border-radius: 6px;
}
QProgressBar {
    border: 1px solid #1F2937;
    border-radius: 4px;
    text-align: center;
    background-color: #090D11;
    color: #C9D1D9;
    font-weight: bold;
}
QProgressBar::chunk {
    background-color: #0284C7;
    border-radius: 3px;
}
"""


class DataQualityAnalyzerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Acoustic Data Quality Analyzer & Sanitization Suite")
        self.resize(1520, 940)
        self.setMinimumSize(1024, 720)

        # Dataset storage
        self.df_raw = None
        self.df_cleaned = None
        self.quality_report = {}
        self.quality_score = 0.0

        self.init_ui()
        self.generate_synthetic_dataset()
        self.run_quality_audit()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # -----------------------------------------------------------------
        # LEFT PANEL: Controls & Configuration
        # -----------------------------------------------------------------
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        scroll_content = QWidget()
        ctrl_layout = QVBoxLayout(scroll_content)

        # 1. Dataset Generation Parameters
        group_gen = QGroupBox("1. SYNTHETIC DATA GENERATOR")
        grid_gen = QGridLayout(group_gen)
        grid_gen.setSpacing(6)

        grid_gen.addWidget(QLabel("Measurement Count:"), 0, 0)
        self.spin_count = QSpinBox()
        self.spin_count.setRange(5000, 50000)
        self.spin_count.setValue(10000)
        self.spin_count.setSingleStep(2500)
        grid_gen.addWidget(self.spin_count, 0, 1)

        grid_gen.addWidget(QLabel("Anomaly Rate (%):"), 1, 0)
        self.spin_anomaly = QDoubleSpinBox()
        self.spin_anomaly.setRange(0.5, 20.0)
        self.spin_anomaly.setValue(5.0)
        self.spin_anomaly.setSingleStep(0.5)
        grid_gen.addWidget(self.spin_anomaly, 1, 1)

        btn_gen = QPushButton("Generate Dataset")
        btn_gen.clicked.connect(self.on_generate_clicked)
        grid_gen.addWidget(btn_gen, 2, 0, 1, 2)

        ctrl_layout.addWidget(group_gen)

        # 2. Quality Detection Parameters
        group_thresh = QGroupBox("2. DETECTOR THRESHOLDS")
        grid_thresh = QGridLayout(group_thresh)
        grid_thresh.setSpacing(6)

        grid_thresh.addWidget(QLabel("Z-Score Threshold:"), 0, 0)
        self.spin_zthresh = QDoubleSpinBox()
        self.spin_zthresh.setRange(1.5, 5.0)
        self.spin_zthresh.setValue(3.0)
        self.spin_zthresh.setSingleStep(0.1)
        grid_thresh.addWidget(self.spin_zthresh, 0, 1)

        grid_thresh.addWidget(QLabel("IQR Multiplier:"), 1, 0)
        self.spin_iqrmult = QDoubleSpinBox()
        self.spin_iqrmult.setRange(1.0, 3.5)
        self.spin_iqrmult.setValue(1.5)
        self.spin_iqrmult.setSingleStep(0.1)
        grid_thresh.addWidget(self.spin_iqrmult, 1, 1)

        grid_thresh.addWidget(QLabel("Flat-line Window (pts):"), 2, 0)
        self.spin_flatwin = QSpinBox()
        self.spin_flatwin.setRange(3, 50)
        self.spin_flatwin.setValue(10)
        grid_thresh.addWidget(self.spin_flatwin, 2, 1)

        grid_thresh.addWidget(QLabel("Saturation SPL (dB):"), 3, 0)
        self.spin_sat_spl = QDoubleSpinBox()
        self.spin_sat_spl.setRange(90.0, 160.0)
        self.spin_sat_spl.setValue(135.0)
        grid_thresh.addWidget(self.spin_sat_spl, 3, 1)

        btn_reaudit = QPushButton("Run Quality Audit")
        btn_reaudit.clicked.connect(self.run_quality_audit)
        grid_thresh.addWidget(btn_reaudit, 4, 0, 1, 2)

        ctrl_layout.addWidget(group_thresh)

        # 3. Actions & Cleaning
        group_clean = QGroupBox("3. SANITIZATION & EXPORT")
        vbox_clean = QVBoxLayout(group_clean)

        btn_clean = QPushButton("Clean Dataset")
        btn_clean.clicked.connect(self.clean_dataset)
        vbox_clean.addWidget(btn_clean)

        btn_export = QPushButton("Export Cleaned Data to CSV")
        btn_export.clicked.connect(self.export_cleaned_csv)
        vbox_clean.addWidget(btn_export)

        ctrl_layout.addWidget(group_clean)
        ctrl_layout.addStretch()

        scroll.setWidget(scroll_content)
        left_layout.addWidget(scroll)

        # -----------------------------------------------------------------
        # RIGHT PANEL: Dashboard Metrics & Visual Plotting Grid
        # -----------------------------------------------------------------
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Quality Metrics Header
        metrics_group = QGroupBox("DATASET QUALITY DASHBOARD")
        grid_metrics = QGridLayout(metrics_group)
        grid_metrics.setSpacing(6)

        self.lbl_score = self.create_metric_card("Quality Score", "-- / 100", grid_metrics, 0, 0)
        self.lbl_total = self.create_metric_card("Total Rows", "0", grid_metrics, 0, 1)
        self.lbl_valid = self.create_metric_card("Valid Samples", "0", grid_metrics, 0, 2)
        self.lbl_invalid = self.create_metric_card("Invalid Samples", "0", grid_metrics, 0, 3)

        self.lbl_outliers = self.create_metric_card("Outliers (Z/IQR)", "0", grid_metrics, 1, 0)
        self.lbl_missing = self.create_metric_card("Missing Values", "0", grid_metrics, 1, 1)
        self.lbl_saturated = self.create_metric_card("Saturated (Clip)", "0", grid_metrics, 1, 2)
        self.lbl_anomalies = self.create_metric_card("Spikes / Flat / Drift", "0", grid_metrics, 1, 3)

        right_layout.addWidget(metrics_group)

        # Graphical Subplots
        plots_group = QGroupBox("DIAGNOSTIC VISUALIZATION ENGINE")
        layout_plots = QVBoxLayout(plots_group)

        self.fig = Figure(figsize=(9, 6), facecolor='#05080A')
        self.canvas = FigureCanvas(self.fig)
        layout_plots.addWidget(self.canvas)

        right_layout.addWidget(plots_group, stretch=1)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([360, 1140])

    def create_metric_card(self, title, default_val, layout, row, col):
        card = QFrame()
        card.setObjectName("metricCard")
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(6, 4, 6, 4)

        lbl_title = QLabel(title.upper())
        lbl_title.setStyleSheet("color: #9CA3AF; font-size: 10px; font-weight: bold;")
        lbl_val = QLabel(default_val)
        lbl_val.setStyleSheet("color: #38BDF8; font-size: 12px; font-weight: bold;")

        vbox.addWidget(lbl_title)
        vbox.addWidget(lbl_val)
        layout.addWidget(card, row, col)
        return lbl_val

    # -------------------------------------------------------------------------
    # Synthetic Dataset Generation Engine (Simulating Sensor Anomalies)
    # -------------------------------------------------------------------------
    def generate_synthetic_dataset(self):
        n = self.spin_count.value()
        rate = self.spin_anomaly.value() / 100.0

        np.random.seed(42)

        # Timestamps (10 Hz sampling rate)
        timestamps = pd.date_range("2026-08-01 00:00:00", periods=n, freq="100ms")

        # Nominal Physics Baseline
        freq_base = np.random.uniform(20.0, 10000.0, n)
        amplitude_base = np.abs(np.sin(2 * np.pi * 0.001 * np.arange(n))) * 5.0 + np.random.normal(0, 0.2, n)
        spl_base = 70.0 + 20.0 * np.log10(np.maximum(amplitude_base, 0.001)) + np.random.normal(0, 0.5, n)
        temp_base = 22.0 + 3.0 * np.sin(2 * np.pi * np.arange(n) / (n / 2)) + np.random.normal(0, 0.1, n)

        # Inject Sensor Imperfection Artifacts
        num_corrupt = int(n * rate)

        # 1. Missing values (NaN)
        idx_missing = np.random.choice(n, size=int(num_corrupt * 0.6), replace=False)
        spl_base[idx_missing[:len(idx_missing)//2]] = np.nan
        temp_base[idx_missing[len(idx_missing)//2:]] = np.nan

        # 2. Outliers & Sensor Spikes
        idx_spikes = np.random.choice(n, size=int(num_corrupt * 0.4), replace=False)
        spl_base[idx_spikes] += np.random.choice([-1, 1], size=len(idx_spikes)) * np.random.uniform(40, 70, len(idx_spikes))

        # 3. Saturation (Clipping at high SPL)
        sat_threshold = self.spin_sat_spl.value()
        idx_sat = np.random.choice(n, size=int(num_corrupt * 0.4), replace=False)
        spl_base[idx_sat] = sat_threshold

        # 4. Flat-line Measurements (Frozen sensor stuck output)
        flat_start = np.random.randint(100, n - 200)
        flat_len = 25
        spl_base[flat_start:flat_start + flat_len] = spl_base[flat_start]

        # 5. Sensor Drift (Linear baseline creep over time)
        drift_start = np.random.randint(100, n - 1000)
        drift_len = 800
        drift_slope = np.linspace(0, 25.0, drift_len)
        spl_base[drift_start:drift_start + drift_len] += drift_slope

        # Assemble DataFrame
        df = pd.DataFrame({
            'timestamp': timestamps,
            'frequency': freq_base,
            'amplitude': amplitude_base,
            'SPL': spl_base,
            'temperature': temp_base,
            'measurement_id': [f"M-{100000+i}" for i in range(n)]
        })

        # 6. Duplicate Measurements
        idx_dups = np.random.choice(n, size=int(num_corrupt * 0.3), replace=False)
        df_dups = df.iloc[idx_dups].copy()
        df = pd.concat([df, df_dups], ignore_index=True)

        self.df_raw = df.copy()
        self.df_cleaned = None

    def on_generate_clicked(self):
        self.generate_synthetic_dataset()
        self.run_quality_audit()
        QMessageBox.information(self, "Dataset Generated", f"Generated synthetic dataset with {len(self.df_raw)} rows incorporating noise, missing values, spikes, and drift.")

    # -------------------------------------------------------------------------
    # Comprehensive Automated Quality Audit Engine
    # -------------------------------------------------------------------------
    def run_quality_audit(self):
        if self.df_raw is None:
            return

        df = self.df_raw.copy()
        total_rows = len(df)

        # 1. Missing Values
        missing_mask = df.isna().any(axis=1)
        cnt_missing = int(missing_mask.sum())

        # 2. Duplicates
        dup_mask = df.duplicated(subset=['measurement_id'], keep='first')
        cnt_duplicates = int(dup_mask.sum())

        # 3. Saturation Detection
        sat_limit = self.spin_sat_spl.value()
        sat_mask = df['SPL'] >= sat_limit
        cnt_saturated = int(sat_mask.sum())

        # 4. Outlier Detection (Z-Score & IQR on valid SPL values)
        valid_spl = df['SPL'].dropna()
        
        # Z-Score
        z_thresh = self.spin_zthresh.value()
        z_scores = np.abs(stats.zscore(valid_spl))
        z_outliers_idx = valid_spl.index[z_scores > z_thresh]

        # IQR
        iqr_mult = self.spin_iqrmult.value()
        q25, q75 = np.percentile(valid_spl, [25, 75])
        iqr = q75 - q25
        lower_bound = q25 - (iqr_mult * iqr)
        upper_bound = q75 + (iqr_mult * iqr)
        iqr_outliers_idx = valid_spl.index[(valid_spl < lower_bound) | (valid_spl > upper_bound)]

        outlier_indices = set(z_outliers_idx).union(set(iqr_outliers_idx))
        outlier_mask = df.index.isin(outlier_indices)
        cnt_outliers = len(outlier_indices)

        # 5. Flat-line Detection
        flat_win = self.spin_flatwin.value()
        spl_diff = df['SPL'].diff().abs()
        flat_mask = (spl_diff == 0).rolling(window=flat_win, min_periods=flat_win).sum() == flat_win
        cnt_flat = int(flat_mask.sum())

        # 6. Sensor Drift Detection (Rolling mean derivative thresholding)
        rolling_mean = df['SPL'].rolling(window=200, min_periods=50).mean()
        drift_rate = rolling_mean.diff().abs()
        drift_mask = drift_rate > 0.05
        cnt_drift = int(drift_mask.sum())

        # Combine Invalid Flags
        invalid_mask = missing_mask | dup_mask | sat_mask | outlier_mask | flat_mask
        cnt_invalid = int(invalid_mask.sum())
        cnt_valid = total_rows - cnt_invalid

        # Calculate Overall Quality Score (0 - 100)
        penalty_missing = (cnt_missing / total_rows) * 30.0
        penalty_outliers = (cnt_outliers / total_rows) * 25.0
        penalty_sat = (cnt_saturated / total_rows) * 20.0
        penalty_dups = (cnt_duplicates / total_rows) * 15.0
        penalty_anom = ((cnt_flat + cnt_drift) / total_rows) * 10.0

        score = max(0.0, 100.0 - (penalty_missing + penalty_outliers + penalty_sat + penalty_dups + penalty_anom))
        self.quality_score = score

        # Store Audit Results
        self.quality_report = {
            'total': total_rows,
            'valid': cnt_valid,
            'invalid': cnt_invalid,
            'missing': cnt_missing,
            'duplicates': cnt_duplicates,
            'saturated': cnt_saturated,
            'outliers': cnt_outliers,
            'flat': cnt_flat,
            'drift': cnt_drift,
            'invalid_mask': invalid_mask,
            'outlier_mask': outlier_mask
        }

        # Update Readout Dashboard
        self.lbl_score.setText(f"{score:.1f} / 100")
        if score >= 85.0:
            self.lbl_score.setStyleSheet("color: #00FF66; font-size: 14px; font-weight: bold;")
        elif score >= 65.0:
            self.lbl_score.setStyleSheet("color: #FFCC00; font-size: 14px; font-weight: bold;")
        else:
            self.lbl_score.setStyleSheet("color: #EF4444; font-size: 14px; font-weight: bold;")

        self.lbl_total.setText(f"{total_rows:,}")
        self.lbl_valid.setText(f"{cnt_valid:,}")
        self.lbl_invalid.setText(f"{cnt_invalid:,}")
        self.lbl_outliers.setText(f"{cnt_outliers:,}")
        self.lbl_missing.setText(f"{cnt_missing:,}")
        self.lbl_saturated.setText(f"{cnt_saturated:,}")
        self.lbl_anomalies.setText(f"{cnt_flat + cnt_drift:,}")

        self.plot_diagnostics()

    # -------------------------------------------------------------------------
    # Sanitization Engine (Clean Dataset)
    # -------------------------------------------------------------------------
    def clean_dataset(self):
        if self.df_raw is None or not self.quality_report:
            return

        inv_mask = self.quality_report['invalid_mask']
        self.df_cleaned = self.df_raw[~inv_mask].copy().reset_index(drop=True)

        QMessageBox.information(
            self, "Dataset Cleaned",
            f"Successfully purged {self.quality_report['invalid']} corrupted rows.\n"
            f"Cleaned dataset now contains {len(self.df_cleaned):,} pristine records."
        )

    def export_cleaned_csv(self):
        export_df = self.df_cleaned if self.df_cleaned is not None else self.df_raw
        if export_df is None:
            QMessageBox.warning(self, "Export Error", "No data available to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Export Dataset CSV", "", "CSV Files (*.csv)")
        if file_path:
            try:
                export_df.to_csv(file_path, index=False)
                QMessageBox.information(self, "Export Success", f"Dataset successfully exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to save CSV file:\n{str(e)}")

    # -------------------------------------------------------------------------
    # Matplotlib Multi-Panel Diagnostic Plots
    # -------------------------------------------------------------------------
    def plot_diagnostics(self):
        self.fig.clear()

        bg_color = '#05080A'
        grid_color = '#13231B'
        cyan_color = '#38BDF8'
        red_color = '#EF4444'
        green_color = '#00FF66'

        # 2x2 Grid Subplots
        gs = self.fig.add_gridspec(2, 2)

        ax_time = self.fig.add_subplot(gs[0, 0])
        ax_hist = self.fig.add_subplot(gs[0, 1])
        ax_box = self.fig.add_subplot(gs[1, 0])
        ax_freq = self.fig.add_subplot(gs[1, 1])

        for ax in [ax_time, ax_hist, ax_box, ax_freq]:
            ax.set_facecolor(bg_color)
            ax.tick_params(colors='#9CA3AF', labelsize=7)
            for spine in ax.spines.values():
                spine.set_color('#1F2937')

        df = self.df_raw
        out_mask = self.quality_report.get('outlier_mask', np.zeros(len(df), dtype=bool))

        # 1. TIME SERIES SPL WITH ANOMALIES HIGHLIGHTED
        ax_time.plot(df.index, df['SPL'], color=cyan_color, linewidth=0.6, alpha=0.7, label='Measured SPL')
        if out_mask.sum() > 0:
            ax_time.scatter(df.index[out_mask], df['SPL'][out_mask], color=red_color, s=12, label='Detected Outlier/Spike', zorder=5)

        ax_time.set_title("TIME SERIES SPL MEASUREMENTS (dB)", color=cyan_color, fontsize=8, fontweight='bold', loc='left')
        ax_time.set_xlabel("Sample Index", color='#9CA3AF', fontsize=7)
        ax_time.set_ylabel("SPL (dB)", color='#9CA3AF', fontsize=7)
        ax_time.grid(True, linestyle=':', linewidth=0.5, color=grid_color)
        ax_time.legend(facecolor='#0B1217', edgecolor=grid_color, labelcolor='#C9D1D9', fontsize=6, loc='upper right')

        # 2. HISTOGRAM OF ACOUSTIC SPL DISTRIBUTION
        valid_spl = df['SPL'].dropna()
        ax_hist.hist(valid_spl, bins=50, color='#0284C7', edgecolor='#05080A', alpha=0.85)
        ax_hist.axvline(self.spin_sat_spl.value(), color=red_color, linestyle='--', linewidth=1.0, label='Saturation Limit')
        ax_hist.set_title("SPL AMPLITUDE PROBABILITY DISTRIBUTION", color=green_color, fontsize=8, fontweight='bold', loc='left')
        ax_hist.set_xlabel("SPL (dB)", color='#9CA3AF', fontsize=7)
        ax_hist.set_ylabel("Count", color='#9CA3AF', fontsize=7)
        ax_hist.grid(True, linestyle=':', linewidth=0.5, color=grid_color)
        ax_hist.legend(facecolor='#0B1217', edgecolor=grid_color, labelcolor='#C9D1D9', fontsize=6, loc='upper right')

        # 3. BOX PLOT FOR OUTLIER BOUNDARY IDENTIFICATION
        box = ax_box.boxplot(valid_spl, vert=False, patch_artist=True,
                             boxprops=dict(facecolor='#1E293B', color=cyan_color),
                             capprops=dict(color='#9CA3AF'),
                             whiskerprops=dict(color='#9CA3AF'),
                             flierprops=dict(marker='o', markerfacecolor=red_color, markersize=3, markeredgecolor='none'),
                             medianprops=dict(color=green_color, linewidth=1.5))
        ax_box.set_title("IQR OUTLIER & WHISKER DISTRIBUTION", color=cyan_color, fontsize=8, fontweight='bold', loc='left')
        ax_box.set_xlabel("SPL (dB)", color='#9CA3AF', fontsize=7)
        ax_box.set_yticklabels([])
        ax_box.grid(True, linestyle=':', linewidth=0.5, color=grid_color)

        # 4. FREQUENCY DISTRIBUTION DENSITY
        ax_freq.hist(df['frequency'].dropna(), bins=40, color='#38BDF8', edgecolor='#05080A', alpha=0.75)
        ax_freq.set_title("MEASUREMENT FREQUENCY BAND OCCUPANCY (Hz)", color=green_color, fontsize=8, fontweight='bold', loc='left')
        ax_freq.set_xlabel("Frequency (Hz)", color='#9CA3AF', fontsize=7)
        ax_freq.set_ylabel("Count", color='#9CA3AF', fontsize=7)
        ax_freq.grid(True, linestyle=':', linewidth=0.5, color=grid_color)

        self.fig.tight_layout()
        self.canvas.draw()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet(DARK_STYLE)

    window = DataQualityAnalyzerApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()