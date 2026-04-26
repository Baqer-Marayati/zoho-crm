#!/usr/bin/env python3
"""
Single-box Address layout for Leads — **UI only** in most orgs.

This repository attempted `PATCH` on the virtual **Address** field (`child_fields`) and on the
layout. Zoho returned:

  `Address field configuration is not supported in this version` (NOT_ALLOWED)

So custom picklists (**Country (Iraq)**, **Province**, **City (Iraq)**) cannot be moved *inside*
the bordered Address compound via API. They appear as separate section fields until changed in
**Setup / layout editor** (if your edition allows adding fields to the address group).

Do this in Zoho (typical path; labels vary by UI version):

1. **Leads → Create Lead → Edit Page Layout**
2. Open **Address Information**
3. Click the **Address** field (the compound), or use the **gear** on that block
4. If you see **subfield** or **fields in address** options, **turn off** anything you do not want
   (e.g. Zip, Coordinates, or legacy Country/State/City if you rely on the Iraq picklists)
5. Drag **Country (Iraq)**, **Province**, and **City (Iraq)** so they sit **directly under** the
   Address block in the **same section** if you cannot merge them into the compound (visual grouping)
6. **Save** the layout

Optional: **Setup → Customization → Modules and Fields → Leads → Address** — some editions list
which lines appear in the address block.

Reference: Zoho’s own pattern for picklist-based address data is often custom fields + workflows
when the compound cannot hold them:  
https://www.zoho.com/crm/resources/solutions/using-picklists-for-address-fields.html

This script prints the above and exits with code 2 (no API call).
"""
from __future__ import annotations

import sys


def main() -> int:
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
