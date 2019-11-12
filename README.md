# dbus-characterdisplay

This service is used to handle the display of menus and alerts on the character display LCD (1602) as well as handle user interaction when available. 

The following behaviours are expected: 
- On devices with 0 buttons: the menus automatically roll
- On devices with 1 buttons: the menus roll, and pressing the button force the rolling
- On devices with 4 buttons: the user can see the available menu list and select the menu to see
