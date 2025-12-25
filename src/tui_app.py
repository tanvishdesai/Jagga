"""
Chat Analyzer TUI - A beautiful Terminal User Interface
Built with Textual and Rich for the WhatsApp/Instagram Chat Analyzer
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, List
import json
import shutil

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header, Footer, Button, Static, Label, 
    Input, Switch, ProgressBar, Log, 
    DirectoryTree, TabbedContent, TabPane,
    Markdown, LoadingIndicator, DataTable
)
from textual.binding import Binding
from textual import work
from textual.worker import Worker, get_current_worker

from rich.console import Console
from rich.text import Text

# Import project modules
from config import WHATSAPP_PATH, INSTAGRAM_PATH, OUTPUT_DIR, GEMINI_ACCOUNT_KEYS, BASE_DIR
from parsers import parse_whatsapp, parse_instagram
from models import UnifiedMessage


# ============================================================================
#                           CUSTOM WIDGETS
# ============================================================================

class FeatureCard(Button):
    """A clickable feature card widget."""
    
    def __init__(self, title: str, description: str, icon: str = "📦", **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.description = description
        self.icon = icon
        self.add_class("feature-card")
        
    def compose(self) -> ComposeResult:
        yield Static(f"{self.icon}\n\n{self.title}", classes="card-content")


class SummaryStatWidget(Static):
    """A widget to display a summary statistic."""
    
    def __init__(self, label: str, value: str, icon: str = "📊", **kwargs):
        super().__init__(**kwargs)
        self.label_text = label
        self.value_text = value
        self.icon = icon
        
    def compose(self) -> ComposeResult:
        yield Horizontal(
            Static(f"{self.icon} {self.label_text}:", classes="stat-label"),
            Static(self.value_text, classes="stat-value"),
            classes="summary-stat"
        )


# ============================================================================
#                           WELCOME SCREEN
# ============================================================================

ASCII_LOGO = """
╔═══════════════════════════════════════════════════════════════════════════════════╗
║                                                                                   ║
║   ██████╗██╗  ██╗ █████╗ ████████╗     █████╗ ███╗   ██╗ █████╗ ██╗  ██╗   ██╗   ║
║  ██╔════╝██║  ██║██╔══██╗╚══██╔══╝    ██╔══██╗████╗  ██║██╔══██╗██║  ╚██╗ ██╔╝   ║
║  ██║     ███████║███████║   ██║       ███████║██╔██╗ ██║███████║██║   ╚████╔╝    ║
║  ██║     ██╔══██║██╔══██║   ██║       ██╔══██║██║╚██╗██║██╔══██║██║    ╚██╔╝     ║
║  ╚██████╗██║  ██║██║  ██║   ██║       ██║  ██║██║ ╚████║██║  ██║███████╗██║      ║
║   ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝       ╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝╚══════╝╚═╝      ║
║                                                                                   ║
╚═══════════════════════════════════════════════════════════════════════════════════╝
"""

class WelcomeScreen(Screen):
    """The welcome/home screen of the application."""
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("s", "push_screen('settings')", "Settings"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Container(id="welcome-container"):
            yield Static(ASCII_LOGO, id="app-title")
            yield Static("🎁 Intelligent Gift Recommendation & Relationship Analysis System", id="app-subtitle")
            
            with Horizontal(id="feature-cards"):
                yield Button("📱\n\nWhatsApp\nChat", id="btn-whatsapp", classes="feature-card")
                yield Button("📸\n\nInstagram\nChat", id="btn-instagram", classes="feature-card")
                yield Button("⚙️\n\nSettings\n", id="btn-settings", classes="feature-card")
                yield Button("📂\n\nPrevious\nResults", id="btn-results", classes="feature-card")
            
            with Horizontal(id="action-buttons"):
                yield Button("🚀 Start Analysis", id="btn-start", variant="success", classes="primary-button")
                yield Button("❓ Help", id="btn-help", classes="secondary-button")
        
        yield Footer()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id
        
        if button_id == "btn-whatsapp":
            self.app.push_screen(FileSelectionScreen(file_type="whatsapp"))
        elif button_id == "btn-instagram":
            self.app.push_screen(FileSelectionScreen(file_type="instagram"))
        elif button_id == "btn-settings":
            self.app.push_screen(SettingsScreen())
        elif button_id == "btn-results":
            self.app.push_screen(PreviousResultsScreen())
        elif button_id == "btn-start":
            self.app.push_screen(ProcessingScreen())
        elif button_id == "btn-help":
            self.app.push_screen(HelpScreen())


# ============================================================================
#                         FILE SELECTION SCREEN
# ============================================================================

class FilteredDirectoryTree(DirectoryTree):
    """A directory tree that can filter by file extensions."""
    
    def __init__(self, path: str, extensions: List[str] = None, **kwargs):
        super().__init__(path, **kwargs)
        self.extensions = extensions or []
    
    def filter_paths(self, paths):
        """Filter paths based on extensions."""
        if not self.extensions:
            return paths
        return [
            path for path in paths
            if path.is_dir() or path.suffix.lower() in self.extensions
        ]


class FileSelectionScreen(Screen):
    """Screen for selecting chat export files."""
    
    BINDINGS = [
        Binding("escape", "pop_screen", "Back"),
        Binding("enter", "select_file", "Select"),
    ]
    
    def __init__(self, file_type: str = "whatsapp", **kwargs):
        super().__init__(**kwargs)
        self.file_type = file_type
        self.selected_file: Optional[Path] = None
        
        # Set extensions based on file type
        if file_type == "whatsapp":
            self.extensions = [".txt"]
            self.title = "📱 Select WhatsApp Export File"
        else:
            self.extensions = [".json"]
            self.title = "📸 Select Instagram Export File"
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Vertical(id="file-browser-container"):
            yield Static(self.title, classes="section-title")
            
            # Current path display
            yield Static(
                f"📂 Project: {BASE_DIR}",
                id="path-display"
            )
            
            # Directory tree - start at project directory
            yield DirectoryTree(str(BASE_DIR), id="file-list")
            
            # Filter bar with buttons
            with Horizontal(id="filter-bar"):
                yield Button("✓ Select File", id="btn-confirm", variant="success")
                yield Button("← Back", id="btn-back", variant="default")
        
        yield Footer()
    
    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Handle file selection in directory tree."""
        self.selected_file = event.path
        path_display = self.query_one("#path-display", Static)
        path_display.update(f"📂 Selected: {event.path}")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-back":
            self.app.pop_screen()
        elif event.button.id == "btn-confirm":
            if self.selected_file:
                # Store the selected file in the app
                if self.file_type == "whatsapp":
                    self.app.whatsapp_file = self.selected_file
                else:
                    self.app.instagram_file = self.selected_file
                
                self.notify(f"✓ Selected: {self.selected_file.name}", severity="information")
                self.app.pop_screen()
            else:
                self.notify("⚠ Please select a file first", severity="warning")


# ============================================================================
#                           SETTINGS SCREEN
# ============================================================================

class SettingsScreen(Screen):
    """Screen for configuring analysis settings."""
    
    BINDINGS = [
        Binding("escape", "pop_screen", "Back"),
        Binding("s", "save_settings", "Save"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with ScrollableContainer(id="settings-container"):
            yield Static("⚙️ Analysis Settings", classes="section-title")
            
            # Input Files Section
            yield Static("───────── 📂 Input Files ─────────", classes="settings-divider")
            
            wa_path = str(getattr(self.app, 'whatsapp_file', WHATSAPP_PATH) or "Not selected")
            yield Static(f"  WhatsApp: {wa_path}", id="wa-path-display")
            yield Button("📁 Browse WhatsApp", id="btn-browse-wa")
            
            ig_path = str(getattr(self.app, 'instagram_file', INSTAGRAM_PATH) or "Not selected")
            yield Static(f"  Instagram: {ig_path}", id="ig-path-display")
            yield Button("📁 Browse Instagram", id="btn-browse-ig")
            
            # Analysis Options Section
            yield Static("───────── 🔧 Analysis Options ─────────", classes="settings-divider")
            
            yield Static("  🤖 Use AI (Gemini API):")
            yield Switch(value=False, id="switch-use-ai")
            
            yield Static("  📊 Message Limit (0 = unlimited):")
            yield Input("0", id="input-limit", placeholder="Enter limit")
            
            yield Static("  🔄 Skip AI Analysis:")
            yield Switch(value=False, id="switch-skip-analysis")
            
            yield Static("  🧪 Dry Run (test only):")
            yield Switch(value=False, id="switch-dry-run")
            
            # API Status Section
            yield Static("───────── 🔑 API Status ─────────", classes="settings-divider")
            
            api_status = "✅ Configured" if GEMINI_ACCOUNT_KEYS else "❌ Not configured"
            api_count = len(GEMINI_ACCOUNT_KEYS) if GEMINI_ACCOUNT_KEYS else 0
            yield Static(f"  Gemini API Keys: {api_status} ({api_count} accounts)", id="api-status")
            
            yield Static("")  # Spacer
            
            # Action buttons
            with Horizontal(id="settings-actions"):
                yield Button("💾 Save", id="btn-save", variant="success")
                yield Button("🚀 Run Analysis", id="btn-run", variant="primary")
                yield Button("← Back", id="btn-back", variant="default")
        
        yield Footer()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-back":
            self.app.pop_screen()
        elif event.button.id == "btn-browse-wa":
            self.app.push_screen(FileSelectionScreen(file_type="whatsapp"))
        elif event.button.id == "btn-browse-ig":
            self.app.push_screen(FileSelectionScreen(file_type="instagram"))
        elif event.button.id == "btn-save":
            self.save_settings()
            self.notify("✓ Settings saved!", severity="information")
        elif event.button.id == "btn-run":
            self.save_settings()
            self.app.push_screen(ProcessingScreen())
    
    def save_settings(self) -> None:
        """Save current settings to app state."""
        self.app.use_ai = self.query_one("#switch-use-ai", Switch).value
        self.app.skip_analysis = self.query_one("#switch-skip-analysis", Switch).value
        self.app.dry_run = self.query_one("#switch-dry-run", Switch).value
        
        limit_input = self.query_one("#input-limit", Input).value
        try:
            self.app.message_limit = int(limit_input) if limit_input else 0
        except ValueError:
            self.app.message_limit = 0


# ============================================================================
#                         PROCESSING SCREEN
# ============================================================================

class ProcessingScreen(Screen):
    """Screen showing analysis progress."""
    
    BINDINGS = [
        Binding("escape", "cancel_processing", "Cancel"),
    ]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._processing = False
        self.current_worker: Optional[Worker] = None
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Container(id="processing-container"):
            # Current task box
            with Vertical(id="current-task-box"):
                yield Static("🔄 Processing Chat Data", id="task-title")
                yield Static("Initializing...", id="current-task")
                yield ProgressBar(total=100, id="progress-bar", show_eta=True)
                yield Static("0 / 0 messages", id="progress-stats")
            
            # Log container
            with Vertical(id="log-container"):
                yield Static("📋 Task Log", id="log-title")
                yield Log(id="task-log", highlight=True, auto_scroll=True)
            
            # Action buttons
            with Horizontal(id="processing-actions"):
                yield Button("❌ Cancel", id="btn-cancel", variant="error", classes="danger-button")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Start processing when screen is mounted."""
        self.run_analysis()
    
    @work(exclusive=True, thread=True)
    def run_analysis(self) -> None:
        """Run the analysis in a background thread."""
        worker = get_current_worker()
        log = self.query_one("#task-log", Log)
        progress_bar = self.query_one("#progress-bar", ProgressBar)
        current_task = self.query_one("#current-task", Static)
        progress_stats = self.query_one("#progress-stats", Static)
        
        def update_log(message: str, level: str = "info"):
            """Thread-safe log update."""
            timestamp = datetime.now().strftime("%H:%M:%S")
            icons = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌", "progress": "→"}
            icon = icons.get(level, "ℹ️")
            self.app.call_from_thread(log.write_line, f"[{timestamp}] {icon} {message}")
        
        def update_progress(value: int, total: int, status: str):
            """Thread-safe progress update."""
            self.app.call_from_thread(progress_bar.update, progress=value)
            self.app.call_from_thread(current_task.update, status)
            self.app.call_from_thread(progress_stats.update, f"{value:,} / {total:,}")
        
        try:
            update_log("Starting analysis pipeline...", "info")
            
            # Get file paths
            wa_file = getattr(self.app, 'whatsapp_file', None) or WHATSAPP_PATH
            ig_file = getattr(self.app, 'instagram_file', None) or INSTAGRAM_PATH
            
            all_messages = []
            
            # Parse WhatsApp
            if wa_file and Path(wa_file).exists():
                update_log(f"Parsing WhatsApp: {Path(wa_file).name}", "progress")
                update_progress(10, 100, "Parsing WhatsApp messages...")
                
                wa_msgs = parse_whatsapp(Path(wa_file))
                all_messages.extend(wa_msgs)
                
                update_log(f"Found {len(wa_msgs):,} WhatsApp messages", "success")
            else:
                update_log("No WhatsApp file found", "warning")
            
            if worker.is_cancelled:
                update_log("Analysis cancelled by user", "warning")
                return
            
            # Parse Instagram
            if ig_file and Path(ig_file).exists():
                update_log(f"Parsing Instagram: {Path(ig_file).name}", "progress")
                update_progress(25, 100, "Parsing Instagram messages...")
                
                ig_msgs = parse_instagram(Path(ig_file))
                all_messages.extend(ig_msgs)
                
                update_log(f"Found {len(ig_msgs):,} Instagram messages", "success")
            else:
                update_log("No Instagram file found", "warning")
            
            if not all_messages:
                update_log("No messages found from any source!", "error")
                return
            
            # Sort messages
            update_progress(40, 100, "Sorting and processing messages...")
            all_messages.sort(key=lambda x: x.timestamp)
            total_msgs = len(all_messages)
            update_log(f"Total messages loaded: {total_msgs:,}", "success")
            
            if worker.is_cancelled:
                return
            
            # Create output directory
            update_progress(50, 100, "Creating output directory...")
            
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            chat_slug = "chat_analysis"
            
            if wa_file and Path(wa_file).exists():
                chat_slug = Path(wa_file).stem.replace(" ", "_").replace(".", "")
            
            run_dir = OUTPUT_DIR / f"{timestamp}__{chat_slug}"
            run_dir.mkdir(parents=True, exist_ok=True)
            
            processed_dir = run_dir / "processed_data"
            processed_dir.mkdir(exist_ok=True)
            
            update_log(f"Created output directory: {run_dir.name}", "success")
            
            if worker.is_cancelled:
                return
            
            # Convert to optimized format
            update_progress(60, 100, "Converting to optimized format...")
            update_log("Converting to optimized Toon format...", "progress")
            
            from optimization import convert_to_optimized_format, save_optimized_json
            
            optimized_data = convert_to_optimized_format(all_messages)
            processed_path = processed_dir / f"processed_{chat_slug}.json"
            saved_paths = save_optimized_json(optimized_data, processed_path)
            
            for path in saved_paths:
                update_log(f"Saved: {Path(path).name}", "success")
            
            # Check settings
            use_ai = getattr(self.app, 'use_ai', False)
            skip_analysis = getattr(self.app, 'skip_analysis', False)
            dry_run = getattr(self.app, 'dry_run', False)
            
            if dry_run:
                update_progress(100, 100, "Dry run complete!")
                update_log("Dry run completed. Exiting before analysis.", "success")
            elif skip_analysis:
                update_progress(100, 100, "Data processing complete!")
                update_log("Skipping analysis phase as requested.", "success")
            elif not use_ai:
                # Generate prompts only
                update_progress(80, 100, "Generating prompts...")
                update_log("Generating prompts for manual use...", "progress")
                
                prompts_dir = run_dir / "prompts"
                prompts_dir.mkdir(exist_ok=True)
                
                from analyzer import get_analysis_system_instruction
                
                system_instruction = get_analysis_system_instruction()
                prompt_file = prompts_dir / "system_instruction.txt"
                
                with open(prompt_file, "w", encoding="utf-8") as f:
                    f.write(system_instruction)
                
                update_log(f"Saved system instruction: {prompt_file.name}", "success")
                update_progress(100, 100, "Prompt generation complete!")
            else:
                # Full AI analysis
                update_progress(70, 100, "Running AI analysis...")
                update_log("Starting Gemini API analysis...", "progress")
                
                # Import analysis functions
                from analyzer import (
                    chunk_messages, analyze_chunk, aggregate_profiles,
                    generate_gift_recommendations, generate_relationship_report
                )
                
                # Chunk messages
                msg_limit = getattr(self.app, 'message_limit', 0)
                msgs_to_analyze = all_messages[-msg_limit:] if msg_limit > 0 else all_messages
                
                chunks = chunk_messages(msgs_to_analyze, chunk_size=300)
                update_log(f"Created {len(chunks)} chunks for analysis", "info")
                
                # Analyze chunks
                chunk_results = []
                for i, chunk in enumerate(chunks):
                    if worker.is_cancelled:
                        return
                    
                    progress = 70 + int((i / len(chunks)) * 20)
                    update_progress(progress, 100, f"Analyzing chunk {i+1}/{len(chunks)}...")
                    update_log(f"Processing chunk {i+1}/{len(chunks)}...", "progress")
                    
                    result = analyze_chunk(i, chunk)
                    if result:
                        chunk_results.append(result)
                
                # Aggregate and generate reports
                update_progress(90, 100, "Generating reports...")
                update_log("Aggregating memory map...", "progress")
                
                memory_map = aggregate_profiles(chunk_results)
                
                # Save memory map
                memory_map_path = processed_dir / f"memory_map_{chat_slug}.json"
                with open(memory_map_path, 'w', encoding='utf-8') as f:
                    f.write(json.dumps(memory_map.__dict__, indent=2, ensure_ascii=False))
                update_log("Memory map saved", "success")
                
                # Generate recommendations
                reports_dir = run_dir / "reports"
                reports_dir.mkdir(exist_ok=True)
                
                update_log("Generating gift recommendations...", "progress")
                recommendations = generate_gift_recommendations(memory_map)
                
                rec_path = reports_dir / f"recommendations_{chat_slug}.md"
                with open(rec_path, 'w', encoding='utf-8') as f:
                    f.write(recommendations)
                update_log("Gift recommendations saved", "success")
                
                # Generate relationship report
                update_log("Generating relationship report...", "progress")
                relationship_report = generate_relationship_report(memory_map)
                
                rel_path = reports_dir / f"relationship_report_{chat_slug}.md"
                with open(rel_path, 'w', encoding='utf-8') as f:
                    f.write(relationship_report)
                update_log("Relationship report saved", "success")
                
                update_progress(100, 100, "Analysis complete!")
            
            # Store results for display
            self.app.last_run_dir = run_dir
            self.app.last_message_count = total_msgs
            
            update_log("=" * 40, "info")
            update_log("✨ All tasks completed successfully!", "success")
            update_log(f"Output saved to: {run_dir}", "info")
            
            # Auto-navigate to results after a delay
            import time
            time.sleep(2)
            
            if not worker.is_cancelled:
                self.app.call_from_thread(self.app.push_screen, ResultsScreen())
            
        except Exception as e:
            update_log(f"Error: {str(e)}", "error")
            import traceback
            update_log(traceback.format_exc(), "error")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-cancel":
            self.action_cancel_processing()
    
    def action_cancel_processing(self) -> None:
        """Cancel the current processing."""
        workers = self.workers
        for worker in workers:
            worker.cancel()
        self.notify("Processing cancelled", severity="warning")
        self.app.pop_screen()


# ============================================================================
#                           RESULTS SCREEN
# ============================================================================

class ResultsScreen(Screen):
    """Screen displaying analysis results."""
    
    BINDINGS = [
        Binding("escape", "go_home", "Back"),
        Binding("h", "go_home", "Home"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Vertical(id="results-main"):
            # Summary box
            with Vertical(id="summary-box"):
                yield Static("✨ Analysis Complete!", id="summary-title")
                
                run_dir = getattr(self.app, 'last_run_dir', None)
                msg_count = getattr(self.app, 'last_message_count', 0)
                
                yield Static(f"  📂 Output: {run_dir.name if run_dir else 'N/A'}")
                yield Static(f"  💬 Messages: {msg_count:,}")
            
            # Results tabs
            with TabbedContent(id="results-tabs"):
                with TabPane("🎁 Gifts", id="tab-gifts"):
                    yield Static(self._load_recommendations(), id="gifts-content")
                
                with TabPane("💖 Relationship", id="tab-relationship"):
                    yield Static(self._load_relationship_report(), id="relationship-content")
                
                with TabPane("📂 Files", id="tab-files"):
                    yield Static(self._list_output_files(), id="files-content")
            
            # Action buttons
            with Horizontal(id="results-actions"):
                yield Button("📁 Open Folder", id="btn-open-folder", variant="primary")
                yield Button("🔄 New Analysis", id="btn-new", variant="success")
                yield Button("🏠 Home", id="btn-home", variant="default")
        
        yield Footer()
    
    def _load_recommendations(self) -> str:
        """Load gift recommendations from file."""
        run_dir = getattr(self.app, 'last_run_dir', None)
        if not run_dir:
            return "No recommendations available."
        
        rec_files = list((run_dir / "reports").glob("recommendations_*.md"))
        if rec_files:
            return rec_files[0].read_text(encoding='utf-8')
        
        prompt_files = list((run_dir / "prompts").glob("*.txt"))
        if prompt_files:
            return f"**Prompt Generated**\n\nSystem instruction saved to:\n`{prompt_files[0]}`\n\nUse this with Google AI Studio for manual analysis."
        
        return "No recommendations generated. Try running with AI enabled."
    
    def _load_relationship_report(self) -> str:
        """Load relationship report from file."""
        run_dir = getattr(self.app, 'last_run_dir', None)
        if not run_dir:
            return "No relationship report available."
        
        rel_files = list((run_dir / "reports").glob("relationship_report_*.md"))
        if rel_files:
            return rel_files[0].read_text(encoding='utf-8')
        
        return "No relationship report generated. Try running with AI enabled."
    
    def _list_output_files(self) -> str:
        """List all output files."""
        run_dir = getattr(self.app, 'last_run_dir', None)
        if not run_dir:
            return "No output files."
        
        lines = [f"📁 {run_dir}\n"]
        
        for item in sorted(run_dir.rglob("*")):
            if item.is_file():
                rel_path = item.relative_to(run_dir)
                size = item.stat().st_size
                size_str = f"{size:,} bytes" if size < 1024 else f"{size/1024:.1f} KB"
                lines.append(f"  📄 {rel_path} ({size_str})")
        
        return "\n".join(lines)
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-home":
            self.app.pop_screen()
            self.app.pop_screen()  # Go back to welcome
        elif event.button.id == "btn-new":
            self.app.pop_screen()
            self.app.pop_screen()  # Go back to welcome
        elif event.button.id == "btn-open-folder":
            run_dir = getattr(self.app, 'last_run_dir', None)
            if run_dir:
                import os
                os.startfile(str(run_dir))
    
    def action_go_home(self) -> None:
        """Navigate back to home."""
        while len(self.app.screen_stack) > 1:
            self.app.pop_screen()


# ============================================================================
#                        PREVIOUS RESULTS SCREEN
# ============================================================================

class PreviousResultsScreen(Screen):
    """Screen for viewing previous analysis results."""
    
    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("b", "go_back", "Back"),
    ]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.run_dirs = []  # Store paths for opening
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Vertical(id="prev-results-container"):
            yield Static("📂 Previous Results", classes="section-title")
            
            # List previous runs
            table = DataTable(id="results-table")
            table.add_columns("Date", "Chat", "Status")
            
            if OUTPUT_DIR.exists():
                for run_dir in sorted(OUTPUT_DIR.iterdir(), reverse=True):
                    if run_dir.is_dir() and "__" in run_dir.name:
                        parts = run_dir.name.split("__", 1)
                        date = parts[0] if parts else "Unknown"
                        chat = parts[1][:35] if len(parts) > 1 else "Unknown"
                        
                        # Check for reports
                        has_reports = (run_dir / "reports").exists()
                        status = "✅ Complete" if has_reports else "📝 Prompts Only"
                        
                        table.add_row(date, chat, status)
                        self.run_dirs.append(run_dir)
            
            yield table
            
            # Action buttons - docked at bottom
            with Horizontal(id="prev-results-actions"):
                yield Button("📂 Open Folder", id="btn-open", variant="primary")
                yield Button("← Back to Home", id="btn-back", variant="default")
        
        yield Footer()
    
    def action_go_back(self) -> None:
        """Go back to the previous screen."""
        self.app.pop_screen()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-back":
            self.app.pop_screen()
        elif event.button.id == "btn-open":
            table = self.query_one("#results-table", DataTable)
            if table.cursor_row is not None and table.cursor_row < len(self.run_dirs):
                run_dir = self.run_dirs[table.cursor_row]
                import os
                os.startfile(str(run_dir))
                self.notify(f"Opened: {run_dir.name}", severity="information")
            else:
                self.notify("Select a row first", severity="warning")


# ============================================================================
#                            HELP SCREEN
# ============================================================================

class HelpScreen(Screen):
    """Screen displaying help information."""
    
    BINDINGS = [
        Binding("escape", "pop_screen", "Back"),
    ]
    
    HELP_TEXT = """
# 🎁 Chat Analyzer - Help Guide

## Quick Start

1. **Select Chat Files**: Click on WhatsApp or Instagram buttons to select your chat export files.
2. **Configure Settings**: Adjust analysis options in the Settings screen.
3. **Run Analysis**: Click "Start Analysis" to begin processing.

## Features

### 📱 WhatsApp Import
- Supports `.txt` export files from WhatsApp
- Format: Export chat → Without media → Save .txt file

### 📸 Instagram Import  
- Supports `.json` export files from Instagram
- Download your data from Instagram Settings → Your Activity → Download Your Information

### ⚙️ Settings

| Option | Description |
|--------|-------------|
| **Use AI** | Enable Gemini API for full analysis |
| **Message Limit** | Limit messages to analyze (0 = all) |
| **Skip Analysis** | Only generate processed data, no AI |
| **Dry Run** | Test file parsing without processing |

### 🤖 AI Mode

When **AI is enabled**, the system will:
- Analyze chat patterns using Gemini API
- Generate personalized gift recommendations
- Create a relationship analysis report
- Build a "memory map" of interests

When **AI is disabled**, the system will:
- Process and format chat data
- Generate prompts for manual use in Google AI Studio

## Keyboard Shortcuts

- `Q` - Quit application
- `S` - Open settings
- `Escape` - Go back
- `Enter` - Select/Confirm

## Output

All results are saved to the `output/` directory with:
- `processed_data/` - Optimized JSON files
- `reports/` - Gift recommendations and relationship reports
- `prompts/` - System prompts for manual AI usage
"""
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with ScrollableContainer(id="help-container"):
            yield Markdown(self.HELP_TEXT)
        
        with Horizontal(id="action-buttons"):
            yield Button("← Back", id="btn-back", variant="primary")
        
        yield Footer()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-back":
            self.app.pop_screen()


# ============================================================================
#                           MAIN APPLICATION
# ============================================================================

class ChatAnalyzerApp(App):
    """The main Chat Analyzer TUI application."""
    
    TITLE = "Chat Analyzer"
    SUB_TITLE = "Intelligent Gift Recommendation System"
    CSS_PATH = "tui_styles.tcss"
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("d", "toggle_dark", "Toggle Dark Mode"),
    ]
    
    # Register screens
    SCREENS = {
        "welcome": WelcomeScreen,
        "settings": SettingsScreen,
        "help": HelpScreen,
        "previous_results": PreviousResultsScreen,
    }
    
    # App state
    whatsapp_file: Optional[Path] = None
    instagram_file: Optional[Path] = None
    use_ai: bool = False
    skip_analysis: bool = False
    dry_run: bool = False
    message_limit: int = 0
    last_run_dir: Optional[Path] = None
    last_message_count: int = 0
    
    def on_mount(self) -> None:
        """Set up the application on mount."""
        # Set default file paths from config
        if WHATSAPP_PATH and Path(WHATSAPP_PATH).exists():
            self.whatsapp_file = Path(WHATSAPP_PATH)
        if INSTAGRAM_PATH and Path(INSTAGRAM_PATH).exists():
            self.instagram_file = Path(INSTAGRAM_PATH)
        
        # Push the welcome screen
        self.push_screen("welcome")
    
    def action_toggle_dark(self) -> None:
        """Toggle dark mode."""
        self.dark = not self.dark


# ============================================================================
#                              ENTRY POINT
# ============================================================================

def main():
    """Run the Chat Analyzer TUI application."""
    app = ChatAnalyzerApp()
    app.run()


if __name__ == "__main__":
    main()
