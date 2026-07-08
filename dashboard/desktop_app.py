import threading
import tkinter as tk
from tkinter import messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from accounting.ledger import InvestmentLedger
from accounting.valuation import KrakenBalanceValuator
from config import (
    ALLOW_LIVE_TRADING,
    LEDGER_DB_PATH,
    LIVE_LOOP_SECONDS,
    MAX_ORDER_NOTIONAL,
    MIN_SIGNAL_CONFIDENCE,
    PAPER_TRADING,
    PORTFOLIO_ALERT_PERCENT,
)
from exchange.client import KrakenClient
from live.bot_service import TradingBotService
from live.trader import AutomatedKrakenTrader


THEME = {
    "night": "#05060d",
    "surface": "#0a0d16",
    "surface_raised": "#101522",
    "primary": "#39ff88",
    "primary_hover": "#70ffab",
    "secondary": "#19e6ff",
    "accent": "#7c3cff",
    "text": "#ededed",
    "muted": "#94a3b8",
    "border_primary": "#285946",
    "border_secondary": "#1d5563",
    "border_accent": "#3d2c69",
    "danger": "#ff4d7d",
}


class RogueCircuitDesktopApp:

    def __init__(
        self,
        root: tk.Tk,
        ledger: InvestmentLedger | None = None,
    ):

        self.root = root
        self.ledger = ledger or InvestmentLedger(LEDGER_DB_PATH)
        self.client = KrakenClient()
        self.valuator = KrakenBalanceValuator(self.client)
        self.trader = AutomatedKrakenTrader(
            client=self.client,
        )

        self.metric_vars = {
            "deposits": tk.StringVar(),
            "withdrawals": tk.StringVar(),
            "net_deposits": tk.StringVar(),
            "current_value": tk.StringVar(),
            "net_growth": tk.StringVar(),
            "growth_percent": tk.StringVar(),
            "mode": tk.StringVar(),
        }
        self.amount_var = tk.StringVar()
        self.note_var = tk.StringVar()
        self.manual_value_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")
        self.service_status_var = tk.StringVar(value="Bot stopped")
        self.max_order_var = tk.StringVar()
        self.min_confidence_var = tk.StringVar()
        self.loop_seconds_var = tk.StringVar()
        self._scroll_remainder = 0.0
        self.bot_service = TradingBotService(
            cycle_runner=self._run_one_trading_cycle,
            loop_seconds=LIVE_LOOP_SECONDS,
            on_success=self._service_cycle_complete,
            on_error=self._service_error,
            on_stop=self._service_stopped,
        )

        self._configure_window()
        self._configure_theme()
        self._load_controls()
        self._build_layout()
        self.refresh()

    def _configure_window(self):

        self.root.title("Rogue Circuit Quant")
        self.root.geometry("1120x760")
        self.root.minsize(980, 680)
        self.root.configure(bg=THEME["night"])

    def _configure_theme(self):

        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")

        self.style.configure(
            ".",
            background=THEME["night"],
            foreground=THEME["text"],
            fieldbackground=THEME["surface_raised"],
            bordercolor=THEME["border_secondary"],
            lightcolor=THEME["border_secondary"],
            darkcolor=THEME["surface"],
            font=("Helvetica", 11),
        )
        self.style.configure(
            "Root.TFrame",
            background=THEME["night"],
        )
        self.style.configure(
            "Header.TFrame",
            background=THEME["night"],
        )
        self.style.configure(
            "Surface.TFrame",
            background=THEME["surface"],
        )
        self.style.configure(
            "Raised.TFrame",
            background=THEME["surface_raised"],
            bordercolor=THEME["border_secondary"],
            relief="solid",
        )
        self.style.configure(
            "TLabel",
            background=THEME["night"],
            foreground=THEME["text"],
        )
        self.style.configure(
            "Title.TLabel",
            background=THEME["night"],
            foreground=THEME["text"],
            font=("Helvetica", 24, "bold"),
        )
        self.style.configure(
            "Eyebrow.TLabel",
            background=THEME["night"],
            foreground=THEME["secondary"],
            font=("Courier", 10, "bold"),
        )
        self.style.configure(
            "Mode.TLabel",
            background=THEME["night"],
            foreground=THEME["primary"],
            font=("Courier", 11, "bold"),
        )
        self.style.configure(
            "CardLabel.TLabel",
            background=THEME["surface_raised"],
            foreground=THEME["muted"],
            font=("Courier", 10, "bold"),
        )
        self.style.configure(
            "Metric.TLabel",
            background=THEME["surface_raised"],
            foreground=THEME["primary"],
            font=("Helvetica", 15, "bold"),
        )
        self.style.configure(
            "Panel.TLabelframe",
            background=THEME["surface"],
            bordercolor=THEME["border_secondary"],
            relief="solid",
        )
        self.style.configure(
            "Panel.TLabelframe.Label",
            background=THEME["surface"],
            foreground=THEME["secondary"],
            font=("Courier", 10, "bold"),
        )
        self.style.configure(
            "Panel.TLabel",
            background=THEME["surface"],
            foreground=THEME["text"],
        )
        self.style.configure(
            "TEntry",
            bordercolor=THEME["border_secondary"],
            fieldbackground=THEME["surface_raised"],
            foreground=THEME["text"],
            insertcolor=THEME["primary"],
            padding=6,
        )
        self.style.map(
            "TEntry",
            bordercolor=[("focus", THEME["secondary"])],
        )
        self.style.configure(
            "Primary.TButton",
            background=THEME["primary"],
            foreground=THEME["night"],
            bordercolor=THEME["primary"],
            focusthickness=0,
            font=("Helvetica", 10, "bold"),
            padding=(10, 7),
        )
        self.style.map(
            "Primary.TButton",
            background=[
                ("active", THEME["primary_hover"]),
                ("pressed", THEME["secondary"]),
            ],
            foreground=[("disabled", THEME["muted"])],
        )
        self.style.configure(
            "Secondary.TButton",
            background=THEME["surface_raised"],
            foreground=THEME["secondary"],
            bordercolor=THEME["border_secondary"],
            focusthickness=0,
            font=("Helvetica", 10, "bold"),
            padding=(10, 7),
        )
        self.style.map(
            "Secondary.TButton",
            background=[
                ("active", "#112233"),
                ("pressed", "#132b36"),
            ],
        )
        self.style.configure(
            "Accent.TButton",
            background=THEME["surface_raised"],
            foreground=THEME["primary"],
            bordercolor=THEME["border_primary"],
            focusthickness=0,
            font=("Helvetica", 10, "bold"),
            padding=(10, 7),
        )
        self.style.configure(
            "Danger.TButton",
            background=THEME["danger"],
            foreground=THEME["night"],
            bordercolor=THEME["danger"],
            focusthickness=0,
            font=("Helvetica", 10, "bold"),
            padding=(10, 7),
        )
        self.style.map(
            "Danger.TButton",
            background=[
                ("active", "#ff7aa0"),
                ("pressed", "#ff9ab5"),
            ],
        )
        self.style.configure(
            "Treeview",
            background=THEME["surface_raised"],
            fieldbackground=THEME["surface_raised"],
            foreground=THEME["text"],
            bordercolor=THEME["border_secondary"],
            rowheight=28,
        )
        self.style.configure(
            "Treeview.Heading",
            background=THEME["surface"],
            foreground=THEME["secondary"],
            bordercolor=THEME["border_secondary"],
            font=("Courier", 10, "bold"),
        )
        self.style.map(
            "Treeview",
            background=[("selected", THEME["accent"])],
            foreground=[("selected", THEME["text"])],
        )

    def _load_controls(self):

        controls = self.ledger.bot_controls(
            max_order_notional=MAX_ORDER_NOTIONAL,
            min_signal_confidence=MIN_SIGNAL_CONFIDENCE,
            loop_seconds=LIVE_LOOP_SECONDS,
        )

        self.max_order_var.set(str(controls.max_order_notional))
        self.min_confidence_var.set(
            str(controls.min_signal_confidence)
        )
        self.loop_seconds_var.set(str(controls.loop_seconds))
        self.trader.max_order_notional = controls.max_order_notional
        self.trader.min_signal_confidence = (
            controls.min_signal_confidence
        )
        self.trader.loop_seconds = controls.loop_seconds

        if controls.emergency_stop:
            self.trader.emergency_stop()
            self.service_status_var.set("Emergency stop active")

    def _build_layout(self):

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        header = ttk.Frame(
            self.root,
            padding=(16, 14, 16, 8),
            style="Header.TFrame",
        )
        header.grid(
            row=0,
            column=0,
            sticky="ew",
        )
        header.columnconfigure(0, weight=1)

        brand = ttk.Label(
            header,
            text="ROGUE CIRCUIT OS",
            style="Eyebrow.TLabel",
        )
        brand.grid(
            row=0,
            column=0,
            sticky="w",
        )

        title = ttk.Label(
            header,
            text="Rogue Circuit Quant",
            style="Title.TLabel",
        )
        title.grid(
            row=1,
            column=0,
            sticky="w",
            pady=(4, 0),
        )

        mode = ttk.Label(
            header,
            textvariable=self.metric_vars["mode"],
            style="Mode.TLabel",
        )
        mode.grid(
            row=1,
            column=1,
            sticky="e",
        )

        self.body_canvas = tk.Canvas(
            self.root,
            bg=THEME["night"],
            bd=0,
            highlightthickness=0,
        )
        self.body_canvas.grid(
            row=1,
            column=0,
            sticky="nsew",
        )
        body_scrollbar = ttk.Scrollbar(
            self.root,
            orient="vertical",
            command=self.body_canvas.yview,
        )
        body_scrollbar.grid(
            row=1,
            column=1,
            sticky="ns",
        )
        self.body_canvas.configure(
            yscrollcommand=body_scrollbar.set,
        )

        body = ttk.Frame(
            self.body_canvas,
            padding=(16, 8, 16, 12),
            style="Root.TFrame",
        )
        self.body_window = self.body_canvas.create_window(
            (0, 0),
            window=body,
            anchor="nw",
        )
        body.bind(
            "<Configure>",
            self._update_body_scroll_region,
        )
        self.body_canvas.bind(
            "<Configure>",
            self._resize_body_window,
        )
        self.body_canvas.bind(
            "<Enter>",
            self._bind_body_mousewheel,
        )
        self.body_canvas.bind(
            "<Leave>",
            self._unbind_body_mousewheel,
        )

        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(1, weight=1)

        self._build_metrics(body)
        self._build_chart(body)
        self._build_controls(body)
        self._build_tables(body)

        footer = ttk.Frame(
            self.root,
            padding=(16, 0, 16, 12),
            style="Root.TFrame",
        )
        footer.grid(
            row=2,
            column=0,
            sticky="ew",
        )
        footer.columnconfigure(0, weight=1)

        ttk.Label(
            footer,
            textvariable=self.status_var,
            style="Eyebrow.TLabel",
        ).grid(
            row=0,
            column=0,
            sticky="w",
        )

        ttk.Button(
            footer,
            text="Refresh",
            command=self.refresh,
            style="Secondary.TButton",
        ).grid(
            row=0,
            column=1,
            sticky="e",
        )

    def _build_metrics(self, parent):

        frame = ttk.Frame(
            parent,
            style="Root.TFrame",
        )
        frame.grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(0, 12),
        )

        for column in range(6):
            frame.columnconfigure(column, weight=1)

        metrics = [
            ("Deposited", "deposits"),
            ("Withdrawn", "withdrawals"),
            ("Net Invested", "net_deposits"),
            ("Current Value", "current_value"),
            ("Net Growth", "net_growth"),
            ("Growth", "growth_percent"),
        ]

        for index, (label, key) in enumerate(metrics):
            card = ttk.Frame(
                frame,
                padding=12,
                style="Raised.TFrame",
            )
            card.grid(
                row=0,
                column=index,
                sticky="ew",
                padx=(0, 8),
            )

            ttk.Label(
                card,
                text=label,
                style="CardLabel.TLabel",
            ).grid(
                row=0,
                column=0,
                sticky="w",
            )
            ttk.Label(
                card,
                textvariable=self.metric_vars[key],
                style="Metric.TLabel",
            ).grid(
                row=1,
                column=0,
                sticky="w",
                pady=(6, 0),
            )

    def _update_body_scroll_region(self, _event=None):

        self.body_canvas.configure(
            scrollregion=self.body_canvas.bbox("all"),
        )

    def _resize_body_window(self, event):

        self.body_canvas.itemconfigure(
            self.body_window,
            width=event.width,
        )

    def _bind_body_mousewheel(self, _event=None):

        self._scroll_remainder = 0.0
        self.root.bind_all(
            "<MouseWheel>",
            self._on_body_mousewheel,
        )
        self.root.bind_all(
            "<Button-4>",
            self._on_body_mousewheel,
        )
        self.root.bind_all(
            "<Button-5>",
            self._on_body_mousewheel,
        )

    def _unbind_body_mousewheel(self, _event=None):

        self._scroll_remainder = 0.0
        self.root.unbind_all("<MouseWheel>")
        self.root.unbind_all("<Button-4>")
        self.root.unbind_all("<Button-5>")

    def _on_body_mousewheel(self, event):

        if getattr(event, "num", None) == 4:
            units = -1
        elif getattr(event, "num", None) == 5:
            units = 1
        else:
            self._scroll_remainder += -event.delta / 120
            units = int(self._scroll_remainder)

            if units == 0:
                return

            self._scroll_remainder -= units

        self.body_canvas.yview_scroll(
            units,
            "units",
        )

    def _build_chart(self, parent):

        chart_frame = ttk.Frame(
            parent,
            style="Raised.TFrame",
            padding=10,
        )
        chart_frame.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=(0, 12),
        )
        chart_frame.rowconfigure(0, weight=1)
        chart_frame.columnconfigure(0, weight=1)

        self.figure = Figure(
            figsize=(7, 4),
            dpi=100,
            facecolor=THEME["surface_raised"],
        )
        self.axis = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(
            self.figure,
            chart_frame,
        )
        canvas_widget = self.canvas.get_tk_widget()
        canvas_widget.configure(
            bg=THEME["surface_raised"],
            highlightthickness=0,
        )
        canvas_widget.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

    def _build_controls(self, parent):

        controls = ttk.Frame(
            parent,
            style="Root.TFrame",
        )
        controls.grid(
            row=1,
            column=1,
            sticky="nsew",
        )
        controls.columnconfigure(0, weight=1)

        ledger_box = ttk.LabelFrame(
            controls,
            text="Investment Ledger",
            padding=12,
            style="Panel.TLabelframe",
        )
        ledger_box.grid(
            row=0,
            column=0,
            sticky="ew",
        )
        ledger_box.columnconfigure(1, weight=1)

        ttk.Label(
            ledger_box,
            text="Amount",
            style="Panel.TLabel",
        ).grid(
            row=0,
            column=0,
            sticky="w",
        )
        ttk.Entry(
            ledger_box,
            textvariable=self.amount_var,
        ).grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(8, 0),
        )

        ttk.Label(
            ledger_box,
            text="Note",
            style="Panel.TLabel",
        ).grid(
            row=1,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(
            ledger_box,
            textvariable=self.note_var,
        ).grid(
            row=1,
            column=1,
            sticky="ew",
            padx=(8, 0),
            pady=(8, 0),
        )

        ttk.Button(
            ledger_box,
            text="Add Deposit",
            command=self.add_deposit,
            style="Primary.TButton",
        ).grid(
            row=2,
            column=0,
            sticky="ew",
            pady=(12, 0),
        )
        ttk.Button(
            ledger_box,
            text="Add Withdrawal",
            command=self.add_withdrawal,
            style="Secondary.TButton",
        ).grid(
            row=2,
            column=1,
            sticky="ew",
            padx=(8, 0),
            pady=(12, 0),
        )

        snapshot_box = ttk.LabelFrame(
            controls,
            text="Portfolio Value",
            padding=12,
            style="Panel.TLabelframe",
        )
        snapshot_box.grid(
            row=1,
            column=0,
            sticky="ew",
            pady=(12, 0),
        )
        snapshot_box.columnconfigure(1, weight=1)

        ttk.Label(
            snapshot_box,
            text="Manual Value",
            style="Panel.TLabel",
        ).grid(
            row=0,
            column=0,
            sticky="w",
        )
        ttk.Entry(
            snapshot_box,
            textvariable=self.manual_value_var,
        ).grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(8, 0),
        )

        ttk.Button(
            snapshot_box,
            text="Record Manual Snapshot",
            command=self.record_manual_snapshot,
            style="Accent.TButton",
        ).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(12, 0),
        )
        ttk.Button(
            snapshot_box,
            text="Refresh Kraken Snapshot",
            command=self.refresh_kraken_snapshot,
            style="Secondary.TButton",
        ).grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(8, 0),
        )

        trading_box = ttk.LabelFrame(
            controls,
            text="Trading",
            padding=12,
            style="Panel.TLabelframe",
        )
        trading_box.grid(
            row=2,
            column=0,
            sticky="ew",
            pady=(12, 0),
        )
        trading_box.columnconfigure(0, weight=1)

        ttk.Button(
            trading_box,
            text="Run One Trading Cycle",
            command=self.run_trading_cycle,
            style="Primary.TButton",
        ).grid(
            row=0,
            column=0,
            sticky="ew",
        )

        ttk.Label(
            trading_box,
            textvariable=self.service_status_var,
            style="Panel.TLabel",
        ).grid(
            row=1,
            column=0,
            sticky="w",
            pady=(10, 0),
        )
        service_buttons = ttk.Frame(
            trading_box,
            style="Surface.TFrame",
        )
        service_buttons.grid(
            row=2,
            column=0,
            sticky="ew",
            pady=(8, 0),
        )
        service_buttons.columnconfigure(0, weight=1)
        service_buttons.columnconfigure(1, weight=1)

        ttk.Button(
            service_buttons,
            text="Start Bot",
            command=self.start_bot_service,
            style="Primary.TButton",
        ).grid(
            row=0,
            column=0,
            sticky="ew",
        )
        ttk.Button(
            service_buttons,
            text="Stop Bot",
            command=self.stop_bot_service,
            style="Secondary.TButton",
        ).grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(8, 0),
        )

        stop_buttons = ttk.Frame(
            trading_box,
            style="Surface.TFrame",
        )
        stop_buttons.grid(
            row=3,
            column=0,
            sticky="ew",
            pady=(8, 0),
        )
        stop_buttons.columnconfigure(0, weight=1)
        stop_buttons.columnconfigure(1, weight=1)

        ttk.Button(
            stop_buttons,
            text="Emergency Stop",
            command=self.emergency_stop,
            style="Danger.TButton",
        ).grid(
            row=0,
            column=0,
            sticky="ew",
        )
        ttk.Button(
            stop_buttons,
            text="Resume",
            command=self.resume_trading,
            style="Accent.TButton",
        ).grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(8, 0),
        )

        risk_box = ttk.LabelFrame(
            controls,
            text="Risk Controls",
            padding=12,
            style="Panel.TLabelframe",
        )
        risk_box.grid(
            row=3,
            column=0,
            sticky="ew",
            pady=(12, 0),
        )
        risk_box.columnconfigure(1, weight=1)

        for row, (label, variable) in enumerate([
            ("Max Order $", self.max_order_var),
            ("Min Confidence", self.min_confidence_var),
            ("Loop Seconds", self.loop_seconds_var),
        ]):
            ttk.Label(
                risk_box,
                text=label,
                style="Panel.TLabel",
            ).grid(
                row=row,
                column=0,
                sticky="w",
                pady=(0 if row == 0 else 8, 0),
            )
            ttk.Entry(
                risk_box,
                textvariable=variable,
            ).grid(
                row=row,
                column=1,
                sticky="ew",
                padx=(8, 0),
                pady=(0 if row == 0 else 8, 0),
            )

        ttk.Button(
            risk_box,
            text="Apply Risk Controls",
            command=self.apply_risk_controls,
            style="Accent.TButton",
        ).grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(12, 0),
        )

    def _build_tables(self, parent):

        tables = ttk.Frame(
            parent,
            style="Root.TFrame",
        )
        tables.grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="nsew",
            pady=(12, 0),
        )
        tables.columnconfigure(0, weight=1)
        tables.columnconfigure(1, weight=1)
        tables.rowconfigure(0, weight=1)
        tables.rowconfigure(1, weight=1)
        tables.rowconfigure(2, weight=1)

        tx_box = ttk.LabelFrame(
            tables,
            text="Recent Deposits / Withdrawals",
            padding=8,
            style="Panel.TLabelframe",
        )
        tx_box.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 8),
        )
        tx_box.columnconfigure(0, weight=1)

        self.transaction_tree = ttk.Treeview(
            tx_box,
            columns=("type", "amount", "note", "created_at"),
            show="headings",
            height=7,
        )
        tx_scrollbar = ttk.Scrollbar(
            tx_box,
            orient="vertical",
            command=self.transaction_tree.yview,
        )
        self.transaction_tree.configure(
            yscrollcommand=tx_scrollbar.set,
        )
        for column, label in [
            ("type", "Type"),
            ("amount", "Amount"),
            ("note", "Note"),
            ("created_at", "Time"),
        ]:
            self.transaction_tree.heading(column, text=label)
        self.transaction_tree.grid(
            row=0,
            column=0,
            sticky="nsew",
        )
        tx_scrollbar.grid(
            row=0,
            column=1,
            sticky="ns",
        )

        trade_box = ttk.LabelFrame(
            tables,
            text="Recent Trades",
            padding=8,
            style="Panel.TLabelframe",
        )
        trade_box.grid(
            row=0,
            column=1,
            sticky="nsew",
        )
        trade_box.columnconfigure(0, weight=1)

        self.trade_tree = ttk.Treeview(
            trade_box,
            columns=("symbol", "side", "quantity", "price", "pnl"),
            show="headings",
            height=7,
        )
        trade_scrollbar = ttk.Scrollbar(
            trade_box,
            orient="vertical",
            command=self.trade_tree.yview,
        )
        self.trade_tree.configure(
            yscrollcommand=trade_scrollbar.set,
        )
        for column, label in [
            ("symbol", "Symbol"),
            ("side", "Side"),
            ("quantity", "Quantity"),
            ("price", "Price"),
            ("pnl", "PnL"),
        ]:
            self.trade_tree.heading(column, text=label)
        self.trade_tree.grid(
            row=0,
            column=0,
            sticky="nsew",
        )
        trade_scrollbar.grid(
            row=0,
            column=1,
            sticky="ns",
        )

        decision_box = ttk.LabelFrame(
            tables,
            text="Decision Journal",
            padding=8,
            style="Panel.TLabelframe",
        )
        decision_box.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=(0, 8),
            pady=(8, 0),
        )
        decision_box.columnconfigure(0, weight=1)

        self.decision_tree = ttk.Treeview(
            decision_box,
            columns=(
                "symbol",
                "action",
                "confidence",
                "executed",
                "reason",
            ),
            show="headings",
            height=6,
        )
        decision_scrollbar = ttk.Scrollbar(
            decision_box,
            orient="vertical",
            command=self.decision_tree.yview,
        )
        self.decision_tree.configure(
            yscrollcommand=decision_scrollbar.set,
        )
        for column, label in [
            ("symbol", "Symbol"),
            ("action", "Signal"),
            ("confidence", "Confidence"),
            ("executed", "Executed"),
            ("reason", "Reason"),
        ]:
            self.decision_tree.heading(column, text=label)
        self.decision_tree.grid(
            row=0,
            column=0,
            sticky="nsew",
        )
        decision_scrollbar.grid(
            row=0,
            column=1,
            sticky="ns",
        )

        strategy_box = ttk.LabelFrame(
            tables,
            text="Strategy Performance",
            padding=8,
            style="Panel.TLabelframe",
        )
        strategy_box.grid(
            row=1,
            column=1,
            sticky="nsew",
            pady=(8, 0),
        )
        strategy_box.columnconfigure(0, weight=1)

        self.strategy_tree = ttk.Treeview(
            strategy_box,
            columns=(
                "symbol",
                "strategy",
                "score",
                "profit",
                "win_rate",
                "drawdown",
                "trades",
            ),
            show="headings",
            height=6,
        )
        strategy_scrollbar = ttk.Scrollbar(
            strategy_box,
            orient="vertical",
            command=self.strategy_tree.yview,
        )
        self.strategy_tree.configure(
            yscrollcommand=strategy_scrollbar.set,
        )
        for column, label in [
            ("symbol", "Symbol"),
            ("strategy", "Strategy"),
            ("score", "Score"),
            ("profit", "Profit"),
            ("win_rate", "Win"),
            ("drawdown", "DD"),
            ("trades", "Trades"),
        ]:
            self.strategy_tree.heading(column, text=label)
        self.strategy_tree.grid(
            row=0,
            column=0,
            sticky="nsew",
        )
        strategy_scrollbar.grid(
            row=0,
            column=1,
            sticky="ns",
        )

        alert_box = ttk.LabelFrame(
            tables,
            text="Alerts",
            padding=8,
            style="Panel.TLabelframe",
        )
        alert_box.grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="nsew",
            pady=(8, 0),
        )
        alert_box.columnconfigure(0, weight=1)

        self.alert_tree = ttk.Treeview(
            alert_box,
            columns=("level", "message", "source", "created_at"),
            show="headings",
            height=5,
        )
        alert_scrollbar = ttk.Scrollbar(
            alert_box,
            orient="vertical",
            command=self.alert_tree.yview,
        )
        self.alert_tree.configure(
            yscrollcommand=alert_scrollbar.set,
        )
        for column, label in [
            ("level", "Level"),
            ("message", "Message"),
            ("source", "Source"),
            ("created_at", "Time"),
        ]:
            self.alert_tree.heading(column, text=label)
        self.alert_tree.grid(
            row=0,
            column=0,
            sticky="nsew",
        )
        alert_scrollbar.grid(
            row=0,
            column=1,
            sticky="ns",
        )

    def refresh(self):

        summary = self.ledger.summary()
        mode = "PAPER" if PAPER_TRADING else "LIVE"
        live_gate = "enabled" if ALLOW_LIVE_TRADING else "blocked"

        self.metric_vars["deposits"].set(
            self._money(summary.deposits)
        )
        self.metric_vars["withdrawals"].set(
            self._money(summary.withdrawals)
        )
        self.metric_vars["net_deposits"].set(
            self._money(summary.net_deposits)
        )
        self.metric_vars["current_value"].set(
            self._money(summary.current_value)
        )
        self.metric_vars["net_growth"].set(
            self._money(summary.net_growth)
        )
        self.metric_vars["growth_percent"].set(
            f"{summary.growth_percent:.2%}"
        )
        self.metric_vars["mode"].set(
            f"{mode} trading | live orders {live_gate}"
        )

        self._refresh_chart()
        self._refresh_tables()

    def add_deposit(self):

        self._record_transaction(self.ledger.add_deposit)

    def add_withdrawal(self):

        self._record_transaction(self.ledger.add_withdrawal)

    def record_manual_snapshot(self):

        try:
            total_value = self._read_positive_amount(
                self.manual_value_var.get()
            )
            self.ledger.record_snapshot(
                total_value=total_value,
                cash_value=total_value,
                positions_value=0.0,
                source="manual",
            )
            self._record_value_alerts(total_value, "manual")
        except ValueError as exc:
            messagebox.showerror(
                "Invalid Snapshot",
                str(exc),
            )
            return

        self.manual_value_var.set("")
        self.status_var.set("Manual portfolio snapshot recorded.")
        self.refresh()

    def refresh_kraken_snapshot(self):

        self._run_background(
            "Refreshing Kraken balance...",
            self._record_kraken_snapshot,
        )

    def run_trading_cycle(self):

        self._run_background(
            "Running one trading cycle...",
            self._run_one_trading_cycle,
        )

    def start_bot_service(self):

        if self.bot_service.is_running():
            self.status_var.set("Bot service is already running.")
            return

        if self.trader.kill_switch.active():
            self.status_var.set(
                "Emergency stop is active. Resume before starting."
            )
            return

        if not self.apply_risk_controls(show_message=True):
            return

        self.bot_service.loop_seconds = self.trader.loop_seconds
        self.service_status_var.set("Bot running")
        self.status_var.set("Bot service started.")
        self.ledger.add_alert(
            "INFO",
            "Bot service started.",
            "dashboard",
        )

        self.bot_service.start()

    def stop_bot_service(self):

        self.bot_service.stop()
        self.service_status_var.set("Bot stopping")
        self.status_var.set("Bot service stop requested.")
        self.ledger.add_alert(
            "INFO",
            "Bot service stop requested.",
            "dashboard",
        )

    def emergency_stop(self):

        self.bot_service.stop()
        self.trader.emergency_stop()
        self.ledger.set_emergency_stop(True)
        self.ledger.add_alert(
            "CRITICAL",
            "Emergency stop activated.",
            "dashboard",
        )
        self.service_status_var.set("Emergency stop active")
        self.status_var.set("Emergency stop activated.")
        self.refresh()

    def resume_trading(self):

        self.trader.resume_trading()
        self.ledger.set_emergency_stop(False)
        self.ledger.add_alert(
            "INFO",
            "Trading resumed from emergency stop.",
            "dashboard",
        )
        self.service_status_var.set("Bot stopped")
        self.status_var.set("Trading resumed. Bot is not running.")
        self.refresh()

    def apply_risk_controls(self, show_message: bool = True) -> bool:

        try:
            max_order = self._read_positive_amount(
                self.max_order_var.get()
            )
            min_confidence = float(self.min_confidence_var.get())
            loop_seconds = self._read_positive_amount(
                self.loop_seconds_var.get()
            )
        except ValueError as exc:
            if show_message:
                messagebox.showerror(
                    "Invalid Risk Controls",
                    str(exc),
                )
            return False

        if not 0 <= min_confidence <= 1:
            if show_message:
                messagebox.showerror(
                    "Invalid Risk Controls",
                    "Minimum confidence must be between 0 and 1.",
                )
            return False

        self.trader.max_order_notional = max_order
        self.trader.min_signal_confidence = min_confidence
        self.trader.loop_seconds = loop_seconds
        self.ledger.set_setting(
            "max_order_notional",
            max_order,
        )
        self.ledger.set_setting(
            "min_signal_confidence",
            min_confidence,
        )
        self.ledger.set_setting(
            "loop_seconds",
            loop_seconds,
        )

        if show_message:
            self.ledger.add_alert(
                "INFO",
                "Risk controls updated.",
                "dashboard",
            )
            self.status_var.set("Risk controls updated.")
            self.refresh()

        return True

    def _record_transaction(self, add_method):

        try:
            amount = self._read_positive_amount(
                self.amount_var.get()
            )
            add_method(
                amount,
                self.note_var.get(),
            )
        except ValueError as exc:
            messagebox.showerror(
                "Invalid Transaction",
                str(exc),
            )
            return

        self.amount_var.set("")
        self.note_var.set("")
        self.status_var.set("Ledger updated.")
        self.refresh()

    def _record_kraken_snapshot(self):

        valuation = self.valuator.snapshot()
        self.ledger.record_snapshot(
            total_value=valuation.total_value,
            cash_value=valuation.cash_value,
            positions_value=valuation.positions_value,
            source="kraken",
        )
        self._record_value_alerts(
            valuation.total_value,
            "kraken",
        )

        return "Kraken portfolio snapshot recorded."

    def _service_cycle_complete(self, message: str):

        self.root.after(
            0,
            lambda message=message: self._complete_background_task(
                message
            ),
        )

    def _service_error(self, exc: Exception):

        self.ledger.add_alert(
            "ERROR",
            str(exc),
            "bot_service",
        )
        self.root.after(
            0,
            lambda exc=exc: self._show_background_error(exc),
        )

    def _service_stopped(self):

        self.root.after(
            0,
            self._mark_bot_stopped,
        )

    def _mark_bot_stopped(self):

        if self.trader.kill_switch.active():
            self.service_status_var.set("Emergency stop active")
            return

        self.service_status_var.set("Bot stopped")

    def _run_one_trading_cycle(self):

        events = self.trader.run_once()
        portfolio_value = self.trader.portfolio.account_value()

        self.ledger.record_snapshot(
            total_value=portfolio_value,
            cash_value=portfolio_value,
            positions_value=0.0,
            source="paper_trader",
        )
        self._record_value_alerts(
            portfolio_value,
            "paper_trader",
        )

        for event in events:
            self.ledger.record_decision(
                symbol=event.symbol,
                strategy=event.strategy,
                action=event.action,
                confidence=event.confidence,
                price=event.price,
                executed=event.executed,
                quantity=event.quantity,
                reason=event.reason,
                order_id=event.order_id,
                mode=event.mode,
            )

            if event.executed:
                self.ledger.add_alert(
                    "INFO",
                    (
                        f"{event.mode.upper()} {event.action} "
                        f"{event.symbol} quantity={event.quantity:.8f}"
                    ),
                    "trader",
                )

        for performance in self.trader.strategy_performance.values():
            self.ledger.record_strategy_performance(
                symbol=performance.symbol,
                strategy=performance.strategy,
                score=performance.score,
                net_profit=performance.net_profit,
                win_rate=performance.win_rate,
                drawdown=performance.drawdown,
                trades=performance.trades,
                rationale=performance.rationale,
            )

        for trade in self.trader.portfolio.closed_trades:
            if getattr(trade, "_ledger_recorded", False):
                continue

            self.ledger.record_trade(
                symbol="paper",
                side="SELL",
                quantity=trade.quantity,
                price=trade.exit_price,
                pnl=trade.pnl,
                source=trade.strategy,
            )
            trade._ledger_recorded = True

        return f"Trading cycle completed with {len(events)} event(s)."

    def _record_value_alerts(
        self,
        total_value: float,
        source: str,
    ):

        snapshots = self.ledger.snapshots(limit=2)

        if len(snapshots) < 2:
            return

        previous = snapshots[-2].total_value

        if previous <= 0:
            return

        change_percent = (total_value - previous) / previous

        if abs(change_percent) < PORTFOLIO_ALERT_PERCENT:
            return

        direction = "up" if change_percent > 0 else "down"
        level = "INFO" if change_percent > 0 else "WARN"

        self.ledger.add_alert(
            level,
            (
                f"Portfolio {direction} {abs(change_percent):.2%} "
                f"from previous snapshot."
            ),
            source,
        )

    def _run_background(self, pending_message: str, task):

        self.status_var.set(pending_message)

        def worker():
            try:
                message = task()
            except Exception as exc:
                self.root.after(
                    0,
                    lambda exc=exc: self._show_background_error(exc),
                )
                return

            self.root.after(
                0,
                lambda: self._complete_background_task(message),
            )

        threading.Thread(
            target=worker,
            daemon=True,
        ).start()

    def _complete_background_task(self, message: str):

        self.status_var.set(message)
        self.refresh()

    def _show_background_error(self, exc: Exception):

        self.status_var.set("Operation failed.")
        messagebox.showerror(
            "Operation Failed",
            str(exc),
        )

    def _refresh_chart(self):

        snapshots = self.ledger.snapshots()
        self.axis.clear()
        self.axis.set_facecolor(THEME["surface_raised"])
        self.axis.set_title(
            "Portfolio Value",
            color=THEME["text"],
            fontsize=13,
            fontweight="bold",
        )
        self.axis.set_ylabel(
            "USD",
            color=THEME["muted"],
        )
        self.axis.tick_params(
            colors=THEME["muted"],
        )

        for spine in self.axis.spines.values():
            spine.set_color(THEME["border_secondary"])

        if not snapshots:
            self.axis.text(
                0.5,
                0.5,
                "Record a portfolio snapshot to start the chart.",
                ha="center",
                va="center",
                color=THEME["muted"],
                transform=self.axis.transAxes,
            )
            self.canvas.draw()
            return

        x_values = list(range(1, len(snapshots) + 1))
        y_values = [
            snapshot.total_value
            for snapshot in snapshots
        ]
        self.axis.plot(
            x_values,
            y_values,
            color=THEME["primary"],
            linewidth=2.5,
        )
        self.axis.fill_between(
            x_values,
            y_values,
            min(y_values),
            color=THEME["accent"],
            alpha=0.16,
        )
        self.axis.grid(
            True,
            color=THEME["secondary"],
            alpha=0.18,
            linewidth=0.8,
        )
        self.canvas.draw()

    def _refresh_tables(self):

        self._clear_tree(self.transaction_tree)
        self._clear_tree(self.trade_tree)
        self._clear_tree(self.decision_tree)
        self._clear_tree(self.strategy_tree)
        self._clear_tree(self.alert_tree)

        for row in self.ledger.transactions():
            self.transaction_tree.insert(
                "",
                "end",
                values=(
                    row["type"],
                    self._money(row["amount"]),
                    row["note"],
                    row["created_at"][:19],
                ),
            )

        for row in self.ledger.trades():
            self.trade_tree.insert(
                "",
                "end",
                values=(
                    row["symbol"],
                    row["side"],
                    f"{row['quantity']:.8f}",
                    self._money(row["price"]),
                    self._money(row["pnl"]),
                ),
            )

        for row in self.ledger.decisions():
            self.decision_tree.insert(
                "",
                "end",
                values=(
                    row["symbol"],
                    row["action"],
                    f"{row['confidence']:.2f}",
                    "yes" if row["executed"] else "no",
                    row["reason"],
                ),
            )

        for row in self.ledger.strategy_performance():
            self.strategy_tree.insert(
                "",
                "end",
                values=(
                    row["symbol"],
                    row["strategy"],
                    f"{row['score']:.2f}",
                    self._money(row["net_profit"]),
                    f"{row['win_rate']:.1%}",
                    f"{row['drawdown']:.1%}",
                    row["trades"],
                ),
            )

        for row in self.ledger.alerts():
            self.alert_tree.insert(
                "",
                "end",
                values=(
                    row["level"],
                    row["message"],
                    row["source"],
                    row["created_at"][:19],
                ),
            )

    def _clear_tree(self, tree):

        for item in tree.get_children():
            tree.delete(item)

    def _read_positive_amount(self, raw: str) -> float:

        try:
            amount = float(raw)
        except ValueError as exc:
            raise ValueError(
                "Enter a valid numeric amount."
            ) from exc

        if amount <= 0:
            raise ValueError(
                "Amount must be greater than zero."
            )

        return amount

    def _money(self, value: float) -> str:

        return f"${value:,.2f}"


def main():
    root = tk.Tk()
    app = RogueCircuitDesktopApp(root)
    root.mainloop()
    return app
