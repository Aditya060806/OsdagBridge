[Bug] Changing Footpath raises AttributeError: CustomWindow has no attribute notify_additional_inputs_footpath

### What happens
Every change of the homepage **Footpath** combo prints a traceback:

```text
File ".../desktop/ui/docks/input_dock.py", line 666, in _on_footpath_changed
    self.parent.notify_additional_inputs_footpath(value)
AttributeError: 'CustomWindow' object has no attribute 'notify_additional_inputs_footpath'
```

The rest of the handler still runs because Qt swallows the exception (`is_require_field_changed` is set before the call), so designs complete. The forwarding the call was meant to do never happens.

It happens on every change (None to Single Side, Single Side to Both Sides, Both Sides back to None): 9 tracebacks for 9 footpath changes across my GUI sessions S1, S5, S6 and the demo recording. Sessions without a footpath change show none.

### Environment
Windows 11, Python 3.12.16 (conda env from `environment.yml`), `dev` @ `d74f56d`, source unmodified.

### Steps to reproduce
`python -m osdagbridge.desktop`, then change Footpath from None to Single Side. The traceback appears in the console.

### Evidence
Console of session S1 (TC02 sets Single Side, TC03 Both Sides, TC04 None): [`S1/console.txt`]({REPO}/testing/results/S1/console.txt).

### Root cause
* [`input_dock.py#L666`](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/desktop/ui/docks/input_dock.py#L666) calls `self.parent.notify_additional_inputs_footpath(value)`.
* `CustomWindow.notify_additional_inputs_footpath()` was removed from `template_page.py` in commit `cacaada` ("Finished Generalization with Typical Section Tab", 2026-06-17). The method it forwarded to, `AdditionalInputs.update_footpath_value()`, no longer exists either. The Additional Inputs dialog now refreshes the footpath-dependent sub-tabs itself when it is opened (`refresh_typical_section()`).

### Suggested fix
Remove the dead call (the dialog is modal, so the footpath cannot change while it is open):

```python
# input_dock.py, _on_footpath_changed()
self.is_require_field_changed = True
# self.parent.notify_additional_inputs_footpath(value)   <- remove
```

### Duplicate check
I checked all open and closed issues on 17 Nov 2026 for `notify_additional_inputs_footpath`, `_on_footpath_changed` and footpath tracebacks, and found none.
