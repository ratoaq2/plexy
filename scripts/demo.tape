# Record with scripts/demo.sh
Output docs/images/demo.gif

Set Shell "bash"
Set FontSize 16
Set Width 1540
Set Height 380
Set Padding 20
Set Theme "Dracula"
Set TypingSpeed 40ms

# Hidden: select the other preference first, so that the visible commands show a change.
Hide
Type `cd /demo && export PS1='$ '`
Enter
Type `plexy --config me.yml preferences -l de -t "Arrival (2016)" -t "Gravity (2013)" dubbed`
Enter
Wait+Screen@120s /changed out of/
Type "clear"
Enter
Type `plexy --config friend.yml preferences -l de -t "Arrival (2016)" -t "Gravity (2013)" original`
Enter
Wait+Screen@120s /changed out of/
Type "clear"
Enter
Show

Sleep 500ms
Type "# Me: the original audio, with Brazilian Portuguese subtitles"
Enter
Type `plexy --config me.yml preferences -l pt-BR -t "Arrival (2016)" -t "Gravity (2013)" original`
Sleep 500ms
Enter
Wait+Screen@120s /changed out of/
Sleep 4s

Type "# My friend: the German audio"
Enter
Type `plexy --config friend.yml preferences -l de -t "Arrival (2016)" -t "Gravity (2013)" dubbed`
Sleep 500ms
Enter
Wait+Screen@120s /to de: German/
Sleep 6s
