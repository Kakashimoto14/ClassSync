# Selected Claude Student redesign — reference preparation

Owner selected `C:/Users/lenovo/Downloads/ClassSync Student App UX Redesign (2).html` as the primary direction. SHA256 `1c09b696be47b60c056af01b669420e4f339ac5bd95dd57312057f732809b71a`. Read-only inspection decoded the outer six-page manifest, then each nested template using standard-library JSON/Base64/gzip with bounded decompression. Inert decoded text is in `C:/Users/lenovo/AppData/Local/Temp/classsync-selected-reference-h_ihmn6h/`; no bundled JavaScript was executed and no fonts/runtime imported.

| Reference | Existing implementation target |
|---|---|
| Mobile Home | StudentHome.tsx, next-class presentation helpers, student-home.css |
| Mobile Day / Desktop Week / Mobile Month | StudentSchedule.tsx, existing workspace/date routing, student-schedule.css |
| Mobile Rooms | StudentHome scheduled rooms + existing RoomDiscoveryPages inventory and detail routes |
| Mobile Alerts | StudentHome alerts branch; preserved separate Announcements route |
| Shared frame | AppShell.tsx and Student-scoped tokens/styles; official logo retained |

Observed reference values: Inter/system font; primary #8A2B45, darker rose #7A2540, tint #F8E9ED, border #EBC9D3, neutral ink #1C1B22. Mobile Home uses390px composition,26px heading,20px featured-card padding/radius, compact source/date line, complete agenda and fixed four-destination navigation. Desktop Week uses248px sidebar and44px navigation targets. These are design references, not academic data. Greetings/counts/classes must remain derived; unsupported reminders/toggles/availability are omitted.

Current gate: latest STATUS records repeated institutional route failure (expected `Student · University`) and an unapplied correction in formatted AppShell JSX. New request explicitly retains the persistent-failure stop gate. No source edit or test retry performed in this reference-preparation session. Request owner approval to apply the known matching label correction and one focused retest; if it passes, continue the selected redesign and required milestone checks. Existing original-data/cloud/commit boundaries persist.
