# VHS tape for CyGuide CLI interface preview
# Render with: TMPDIR=/tmp vhs assets/cli.tape && rm -f /tmp/cli.gif

Output "/tmp/cli.gif"

Set Shell "bash"
Set FontSize 14
Set Width 1200
Set Height 1100
Set Padding 20
Set WindowBar Colorful
Set WindowBarSize 40
Set Margin 20
Set MarginFill "#1e1e2e"
Set BorderRadius 10
Set Theme "Catppuccin Mocha"

Hide
Type "export PATH=$PWD/.venv/bin:$PATH"
Enter
Type "clear"
Enter
Sleep 500ms
Show

Type "cyg --help"
Sleep 500ms
Enter
Sleep 2s
Screenshot "assets/cli.png"
Sleep 500ms
