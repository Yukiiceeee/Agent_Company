import os
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "llm_output": "dim italic white"
})

console = Console(theme=custom_theme)

class SimulationLogManager:
    def __init__(self, log_dir="../logs"):
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(log_dir, f"sim_run_{timestamp}.md")
        
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write(f"# Simulation Log - {timestamp}\n\n")

    def _write_file(self, content: str):
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(content + "\n")

    def log_header(self, title: str):
        console.rule(f"[bold blue]{title}[/]")
        self._write_file(f"\n## {title}\n")

    def log_event(self, agent_name: str, event_type: str, message: str, color="info"):
        time_str = datetime.now().strftime("%H:%M:%S")
        console.print(f"[{time_str}] [bold]{agent_name}[/]: [{color}]{message}[/]")
        self._write_file(f"- **{time_str}** | **{agent_name}** | {event_type} | {message}")

    def log_llm_content(self, agent_name: str, content: str, title="Thinking"):
        console.print(Panel(
            content,
            title=f"🤖 {agent_name} - {title}",
            border_style="blue",
            style="llm_output"
        ))
        
        self._write_file(f"\n> **{agent_name} ({title})**:\n> \n> {content.replace(chr(10), chr(10)+'> ')}\n")

    def log_table(self, title: str, columns: list, rows: list):
        table = Table(title=title)
        for col in columns:
            table.add_column(col, justify="center")
        for row in rows:
            table.add_row(*[str(r) for r in row])
            
        console.print(table)
        
        md_table = f"\n### {title}\n| {' | '.join(columns)} |\n| {' | '.join(['---']*len(columns))} |\n"
        for row in rows:
            md_table += f"| {' | '.join(str(r) for r in row)} |\n"
        self._write_file(md_table)

    def log_success(self, message: str):
        console.print(f"✅ [success]{message}[/]")
        self._write_file(f"\n**✅ SUCCESS:** {message}\n")

    def log_error(self, message: str):
        console.print(f"❌ [error]{message}[/]")
        self._write_file(f"\n**❌ ERROR:** {message}\n")

LOGGER = SimulationLogManager()