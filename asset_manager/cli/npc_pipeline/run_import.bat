@echo off
set BLENDER_EXECUTABLE=C:\Dev\tools\blender-4.4.0-windows-x64\blender.exe
REM NPC Model Import Pipeline — runs every 12 hours via Windows Task Scheduler
cd /d "C:\Dev\Asset Manager"
"C:\Dev\Asset Manager\.venv\Scripts\python.exe" -m asset_manager.cli.npc_pipeline.import_npcs >> "C:\Dev\Asset Manager\asset_manager\cli\npc_pipeline\_import.log" 2>&1
