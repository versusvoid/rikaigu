Coming in 1.0.0
============

* Most background rewritten in C++ and transpiled into asm.js.
* Three(!) times memory consumption reduction.
* Suffixoid expressions are recognaized and shown alongside words (can be turned off).
* Text grabbing from more HTML interface elements.
* Autostart option.

Version 0.9.4
=============

* Search in textarea/input works again.
* Async dictionary load (thanks to [@JakeH](https://github.com/JakeH) for idea).
* Fix katakana to hiragana conversion when creating dictionaries.
* Move scratchpad link to `browserAction`'s popup (Alt+S no longer used, fixes [#1](https://github.com/versusvoid/rikaigu/issues/1)).
* Repository structure reorganized a little.

Version 0.9.3
=============

* Fix some broken inflections.
* Use frequenices from wiktionary to order entries.
* After search in words dictionary try search names dictionary for longer match.

Version 0.9.2
=============

* Scratchpad to check copypasted text (opened by Alt+S when rikaigu is enabled).
* Error fixed when hovering over empty select.
* Rikagu can cross comment nodes when selecting text.
* All stylings comes with `!important`. Ugly but reliable.
* Tip in corner how to reenable definitions when in readings-only mode.
* Horisontal line to separate dictionary entries in readings-only mode.
* Default dictionary option.
* Expand classification codes for names dictionary.

Version 0.9.1
=============

* Common popup's css rules moved to a [single file](css/popup-common.css).
* Gray color for uncommon writings/readings.
* Grouping writings with same readings.

Version 0.9.0
=============

* Configurable delay before popup shows up.
* Option to show popup only while specific modificator key being pressed.
* Fixed state indicator.
* Options are updated when edited.
* More recognized inflections.
* More recognized writing variations for words (身うごきー身動き).
* Update to expanded EDICT. More writing variations are displayed as one entry.
* Updated dictionary.
