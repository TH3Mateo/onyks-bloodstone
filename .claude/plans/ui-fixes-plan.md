# Plan wdrożenia poprawek — onyks-bloodstone (start od UI)

## Kontekst

Projekt to baza komponentów PCB (Altium) — FastAPI backend (`backend/`) + Vue 3 SPA frontend (`frontend/`, Vite, Vue Router, prywatna biblioteka komponentów `onyks-web-ui-system` instalowana z githuba, niezvendorowana w tym repo). `issues.json` zawiera 19 zgłoszeń. Użytkownik poprosił o zaplanowanie wdrożenia wszystkich poprawek, zaczynając od UI.

Ustalenia z użytkownikiem:
- **#10 (Dashboard)** — ująć w planie mimo zależności od niedokończonego systemu aktualizacji przez SVN hooks (część UI da się zrobić od razu, część backendowa zostaje jako follow-up).
- **#12 (uprawnienia)** — pominąć w tej turze (świadomy stan testowy, nie bug).

Kolejność: najpierw izolowane/szybkie poprawki UI, potem średnie (layout, wyszukiwarka, dashboard), na końcu funkcje wymagające zmian schematu DB (brak Alembic w projekcie — każda zmiana schematu wymaga ręcznego `ALTER TABLE`).

---

## Etap 1 — szybkie, izolowane poprawki UI ✅ WDROŻONE (2026-09-16)

### #17 — etykiety "Library Reference/Path" → "Symbol Reference/Path" ✅
**Pliki:** `frontend/src/components/ElementForm.vue` (~linie 178-197), `frontend/src/views/ManagementView.vue` (definicje kolumn, ~linie 59-65).
**Zmiana:** zmienić tylko widoczne etykiety/placeholdery UI. NIE zmieniać `key` w definicji kolumn ani nazw pól w `frontend/src/utils/db.js`, `backend/models.py` (`library_ref`/`library_path`), `backend/schemas.py`, `backend/utils.py` — to czysto kosmetyczna zmiana, zero ruszania API/DB.
**Blockery:** brak.

### #16 — Footprint 2/3 widoczne dopiero po uzupełnieniu Footprint 1 i symbolu ✅
**Pliki:** `frontend/src/components/ElementForm.vue` (sekcje Footprint No.2/No.3, ~linie 218-256).
**Zmiana:** owinąć całe sekcje (nie tylko przycisk Select) w `v-if`. Footprint 2 wymaga wypełnionego footprint1 + symbolu (`libraryReference`/`libraryPath`); Footprint 3 dodatkowo wymaga wypełnionego footprint2 (progresja 1→2→3). Warto wydzielić `computed` (`footprint1Filled`, `symbolFilled`, `footprint2Filled`) dla czytelności.
**Blockery:** brak.

### #7 — "Create Similar" ma działać jak "Duplicate" — ROZWIĄZANE, brak zmian kodu
**Ustalenie użytkownika:** "Duplicate" robi dokładnie to co trzeba — issue opisuje stan sprzed naprawy, po prostu nie zostało zamknięte w trackerze. **Akcja: zamknąć issue #7, zero zmian w kodzie.**

### #8 — Przeglądarka footprintów: ESC zamyka dialog, jedno kliknięcie w nawigacji ✅ (część ESC), ❌ blocker (nawigacja)
**Pliki:** `frontend/src/components/RepositoryModelSelector.vue` (owija `<onyks-dialog>`).
**Zmiana (możliwa tutaj):** dodać własny listener `keydown` (Escape) w `RepositoryModelSelector.vue`, programowo zamykający dialog (`dialog.value.open = false`), niezależnie od zachowania biblioteki.
**Zmiana NIEMOŻLIWA bez zmian zewnętrznych:** ujednolicenie liczby kliknięć w nawigacji folderów — logika `@enter-folder` leży wewnątrz `<onyks-file-explorer>` z biblioteki `onyks-web-ui-system`, której kodu nie ma w tym repo.
**Blocker (zewnętrzny, do zgłoszenia w repo biblioteki):** część dot. nawigacji folderów wymaga zmiany w osobnym repozytorium `onyks-web-ui-system`.

---

## Etap 2 — poprawki średniej wielkości

### #15 — Przeprojektowanie układu formularza dodawania elementu ✅ WDROŻONE (2026-09-16)
**Pliki:** `frontend/src/components/ElementForm.vue` (cały plik).
**Zmiana:** zastąpić obecny płaski 2-kolumnowy grid wyraźnie rozdzielonymi sekcjami (Basic Info / Symbol / Footprinty / Suppliers / Datasheet), np. jako osobne `onyks-card`/`onyks-container` z nagłówkami i większym `gap`/`padding`, responsywnie (`cols` zależne od szerokości, wzorem istniejącego `useWindowSize`).
**Kolejność:** wykonać RAZEM z #16 i #17 (ten sam plik) w jednym PR, żeby uniknąć powtórnego przerabiania layoutu. Rekomendowana konsultacja makiety z użytkownikiem przed kodowaniem (zmiana czysto estetyczna, screenshot referencyjny jest w issue #15).
**Blockery:** brak technicznych.

### #6 + #13 — Wyszukiwarka i filtrowanie w ManagementView (połączone) ✅ WDROŻONE (2026-09-16)
**Kluczowe ustalenie:** `BasicTable.vue`/`ManagementView.vue` używają paginacji **serwerowej** (`GET /element/list?limit&skip`, backend `backend/main.py:215-238`) — backend nie obsługuje dziś żadnego parametru wyszukiwania. Czysto frontendowe filtrowanie przefiltrowałoby tylko załadowaną stronę (do ~50 rekordów), nie cały zbiór. **To wymaga zmiany backendu**, mimo że temat jest "UI" — flagujemy to wprost jako odstępstwo od "tylko UI".

**Pliki:** `backend/main.py` (endpoint `elementList`, dodać `search`, `table`/`tables` param), `frontend/src/utils/api.js` (`element.list`), `frontend/src/views/ManagementView.vue`, `frontend/src/components/ColumnsCheckboxes.vue` (zostaje tylko dla widoczności kolumn — nowy, osobny komponent `CategoryFilter.vue` dla filtrów kategorii), `frontend/src/components/BasicTable.vue` (wrapper na `update` z dodatkowymi parametrami).

**Zmiana:**
1. **#13** — pole tekstowe wyszukiwania nad tabelą, debounce ~300ms, parametr `search` do backendu.
2. **#6.1** — panel filtrów kategorii (checkboxy per tabela) z przyciskami Reset/Select all, stan zapisywany w `localStorage` (pierwsze użycie w projekcie — dodać mały helper `frontend/src/utils/storage.js`), odczytywany przy `onMounted`.
3. **#6.2** — przenieść `<BasicButtonsPanel>` (akcje Add/Edit/Delete/Duplicate/...) w `ManagementView.vue` z pozycji PRZED tabelą na pozycję PO tabeli/filtrach — nawbar jest `sticky`, więc to realnie skraca scroll powrotny na małych oknach.
4. **#6.3** — Edytuj/Dodaj/Duplikuj już nawigują w tej samej karcie (`router.push`, potwierdzone — `window.open` jest używany wyłącznie dla PDF datasheet). Zachowanie stanu filtrów po powrocie załatwia się automatycznie dzięki persystencji z punktu 2.

**Blockery:** wymaga wspólnego PR-a frontend+backend; do ustalenia z użytkownikiem czy filtr kategorii ma być osobnym komponentem od `ColumnsCheckboxes.vue` (rekomendowane: tak).

### #11 — Tabela elementów rozszerzalna na całą szerokość ✅ WDROŻONE (2026-09-16)
**Pliki:** `frontend/src/App.vue` (`main { max-width: 1024px }`, ~linie 50-57), `frontend/src/views/ManagementView.vue`.
**Zmiana:** `provide/inject` z `App.vue` sterujące klasą `full-width` na `<main>` (CSS override `max-width: none`), przełącznik (przycisk/ikona) w `ManagementView.vue` nad tabelą. `BasicTable.vue` już ma `width: 100%`, więc rozciągnie się automatycznie.
**Blockery:** brak, do ustalenia tylko czy stan przełącznika ma być zapamiętywany w `localStorage` (rekomendacja: tak, spójnie z #6).

### #10 — Dashboard: przywrócenie karty "Repository statistics" ✅ WDROŻONE (część UI, 2026-09-16)
**Pliki:** `frontend/src/views/DashboardView.vue` (zakomentowany blok, ~linie 106-125).
**Zmiana UI (do zrobienia teraz):** odkomentować kartę — dane (`repositoryStatistics`) są już pobierane i podpięte. Dodać subtelny wizualny wskaźnik ("dane orientacyjne / w budowie"), bo backend nadal zwraca stuby.
**Zakres backendowy (POZA tą turą, follow-up):** `/repository/statistics` (`backend/main.py:649-656`) zwraca zahardkodowane wartości (1/2/3/4) — realne dane wymagają dokończenia systemu aktualizacji przez SVN hooks.
**Blockery:** brak dla części UI; część backendowa jawnie odłożona.

---

## Etap 3 — funkcje wymagające zmian schematu DB / większego zakresu backendowego

**Uwaga ogólna:** brak Alembic w projekcie (`Base.metadata.create_all` nie dodaje kolumn do istniejących tabel) — każda zmiana schematu w tym etapie wymaga ręcznego `ALTER TABLE` na bazie. Warto rozważyć wprowadzenie Alembic jako osobne zadanie infrastrukturalne przed etapem 3.

### #5 — Manufacturer Part Number — ROZWIĄZANE, brak zmian kodu
**Ustalenie użytkownika:** potwierdzone, że mechanizm "dystrybutor + numer katalogowy u dystrybutora" (`Element.suppliers` JSONB + `SuppliersSelector.vue`) w pełni pokrywa tę potrzebę. **Akcja: zamknąć issue #5, zero zmian w kodzie.**

### #2 + #3 + #19 — Zakładka Ustawienia + pliki .DbLib (Altium) i .kicad_dbl (KiCad) ✅ WDROŻONE (2026-09-17)

**Zaimplementowane:**
- `backend/utils.py`: `getCategoryViewMap`/`getSupplierColumnMap` (refaktor współdzielony z generatorem widoków), `generateAltiumDbLib(...)` (buduje pełny plik INI na podstawie realnego przykładu dostarczonego przez użytkownika — `onyks_database.DbLib` — z pustym `User ID=`/`Password=` jako template), `generateKicadDbl(...)` (JSON wg oficjalnego schematu z kodu źródłowego KiCada, `common/database/database_lib_settings.cpp`, zweryfikowanego bezpośrednio z repozytorium GitLab).
- `backend/main.py`: naprawiony `GET /server/identity` (zwraca statyczne dane: nazwa repo SVN, host/port/nazwa bazy — **nigdy loginu/hasła**, bo appka nie ma w ogóle systemu sesji/logowania per-user — patrz #1), nowe `GET /settings/dblib` i `GET /settings/kicad-dbl` (generowane w 100% dynamicznie przy każdym żądaniu, zero cache'owania na dysku — nowa kategoria od razu widoczna przy kolejnym pobraniu).
- `frontend/src/views/SettingsView.vue` (nowy), trasa `/settings`, link w nawigacji.
- Oba pliki mapują kolumny `HelpURL`/`Symbols`/`Footprints` (patrz #4/#19 niżej) na specjalne mechanizmy Altium (`HelpUrl`, `[Library Ref]` itd.) i KiCada (pole nazwane dokładnie „Datasheet", kolumny `symbols`/`footprints` w formacie `Nickname:Name`).
- Connection string w obu plikach ma puste `username`/`password` (do samodzielnego uzupełnienia), ale wypełniony host/port/nazwę bazy.

**Zweryfikowane:** oba endpointy przetestowane curlem, zwracają poprawnie sformatowane pliki; strona Ustawień otwiera się (HTTP 200).

**Ograniczenie do świadomości:** `/server/identity` NIE pokazuje danych zalogowanego użytkownika (login/hasło do SVN itp.), bo ta aplikacja webowa nie ma w ogóle mechanizmu logowania/sesji per-user (potwierdzone przy #1) — pokazuje tylko statyczne dane serwera. Pełna realizacja pierwotnego opisu #2 (dane KONKRETNEGO zalogowanego użytkownika) wymaga najpierw zbudowania systemu logowania w tej aplikacji — osobne, znacznie większe zadanie, poza zakresem tej tury.

### #2 + #3 — pierwotny (częściowo nieaktualny) plan poniżej, zachowany dla historii:
**Pliki:** nowy `frontend/src/views/SettingsView.vue`, `frontend/src/router/index.js` (trasa `/settings`), `frontend/src/App.vue` (link nawigacyjny), `backend/main.py` (naprawić `GET /server/identity`, ~linie 658-659 — obecnie funkcja ma pomyłkową nazwę po copy-paste i zwraca statyczny string), nowy endpoint generujący `.DbLib`.
**Zmiana:** Settings pokazuje login/username i statyczne dane połączenia (host/port/nazwa DB, SVN URL) — **nigdy hasła** (ani DB, ani SVN, ani ODBC; `private.users.password` to hash bcrypt i nie powinien w ogóle trafiać do API). Przycisk "Download .DbLib" generujący plik z pustym `username=`/`password=` jako template.

**Wymaganie użytkownika (2026-09-16):** plik .DbLib musi automatycznie odzwierciedlać bieżący stan kategorii/tabel w bazie — gdy ktoś doda nową tabelę kategorii, wygenerowany plik ma od razu zawierać jej definicję, bez ręcznej edycji. Rozwiązanie: **generować plik w 100% dynamicznie przy każdym żądaniu pobrania** (nie cache'ować statycznego pliku na dysku) — endpoint backendowy przy każdym wywołaniu odpytuje bieżącą listę tabel (`private.tables`, tak jak `table.list`) i dla każdej z nich dołącza sekcję/tabelę w .DbLib wskazującą na odpowiadający jej widok SQL wygenerowany przez `dbCreateOrUpdateElementViews` (`backend/utils.py:109-141` — to już DZIAŁA dynamicznie per-tabela, .DbLib tylko musi to samo wyliczenie tabel wykorzystać przy budowaniu pliku). Dzięki temu nie ma osobnego mechanizmu synchronizacji do utrzymania — "aktualność" pliku wynika wprost z tego, że jest zawsze generowany na żądanie z aktualnego stanu bazy, a nie zapisywany raz i edytowany ręcznie.
**Blockery:** wymaga review bezpieczeństwa (zero haseł w odpowiedziach API); dokładny format `.DbLib` do zweryfikowania na realnym przykładzie Altium przed implementacją.

### #4 — Pole Datasheet: URL zamiast/obok PDF ✅ WDROŻONE (2026-09-17, inaczej niż pierwotnie zaplanowano)

**Zmiana względem pierwotnego planu:** zamiast nowej, ręcznie wypełnianej kolumny `datasheetUrl` w `elements` (co okazało się błędnym zrozumieniem issue), ostatecznie zaimplementowano to jako **w pełni wyliczaną kolumnę w widokach SQL** — `HelpURL` (`backend/utils.py`, `dbCreateOrUpdateElementViews`): `CASE WHEN datasheet THEN '<PUBLIC_FILES_URL>' || uuid::text || '.pdf' ELSE NULL END`. **Zero zmian schematu `elements`** — żadnego ALTER TABLE, żadnej migracji. Nowa zmienna środowiskowa `PUBLIC_FILES_URL` w `.env`/`example.env` (ustawiona na `http://DBserver:8113/files/` — nazwa hosta serwera w sieci lokalnej, do zweryfikowania czy rozpoznawana przez wszystkie stacje robocze przez NetBIOS lub wpis w routerze). Zweryfikowane bezpośrednim zapytaniem SQL do widoku (`HelpURL` zwraca poprawny link).

Przy okazji dodano też dla KiCada (patrz #19 niżej) kolumny `Symbols` (`<nazwa_pliku_symbolu_bez_rozszerzenia>:<library_ref>`) i `Footprints` (analogicznie dla footprint 1) w tych samych widokach, w formacie `LibraryNickname:Name` potwierdzonym przez badanie oficjalnej dokumentacji KiCad (docs.kicad.org, sekcja Database Libraries). Założenie: nickname biblioteki w KiCad = nazwa pliku SchLib/PcbLib bez rozszerzenia — wymaga, żeby użytkownicy KiCada zarejestrowali swoje biblioteki pod dokładnie taką nazwą.

### #4 — pierwotny (nieaktualny) plan poniżej, zachowany dla historii:
**Pliki:** `backend/models.py` (nowa kolumna `datasheetUrl`/`datasheet_url`), `backend/schemas.py`, `backend/utils.py` (widok SQL), `backend/main.py` (routes create/edit/duplicate), `frontend/src/components/ElementForm.vue`/`DatasheetPicker.vue`, `frontend/src/utils/db.js`.
**Zmiana:** nowa, opcjonalna kolumna niezależna od istniejącego `datasheet` (Boolean = czy jest PDF) — element może mieć PDF, URL, oba lub żadne. W widoku `details` link otwierający URL w nowej karcie.
**Blockery:** wymaga ręcznej migracji (`ALTER TABLE ... ADD COLUMN datasheet_url`) + aktualizacji widoku SQL używanego przez `.DbLib`/Altium. Zalecane robić razem z #18 (jedna migracja zamiast dwóch).

### #18 — Wiele datasheetów na element 🔶 BACKEND WDROŻONY (2026-09-17), frontend w toku
**Backend (gotowe):** nowa tabela `private.element_documents` (`id`, `element_uuid` FK→`elements.uuid` `ON DELETE CASCADE`, `label`, `filename`, `created_at`) w `backend/models.py` — **utworzona automatycznie** przez `Base.metadata.create_all` przy starcie backendu, **bez ręcznej migracji** (to nowa tabela, nie zmiana istniejącej). Nowe endpointy w `backend/main.py`: `GET/POST /element/{id}/documents`, `DELETE /element/{id}/documents/{document_id}`. Pliki przechowywane w tym samym `UPLOAD_DIR` co dotychczasowy pojedynczy PDF, pod nazwą `doc_{id}.pdf` (brak kolizji z konwencją `{uuid}.pdf` głównego datasheetu). `elementDelete` rozszerzony o kasowanie plików powiązanych dokumentów przy usuwaniu elementu. Zweryfikowane: backend startuje bez błędów, tabela istnieje w bazie.
**Frontend (do zrobienia):** nowy komponent zarządzania listą dodatkowych dokumentów (upload/usuń, z etykietą typu), widoczny tylko w widoku edit/details (element musi już istnieć — ma uuid).
**Blockery:** brak — jedyna migracja, jakiej się obawialiśmy (dot. `datasheet_url`), okazała się niepotrzebna po korekcie #4 (patrz wyżej) — więc cała ta zmiana wymagała zera ręcznej ingerencji w istniejące tabele.

---

## Poza zakresem tej tury

- **#1** (tworzenie użytkowników Postgres z web UI — obecnie tylko skrypt `other/add_user.py`, wspólna rola `appuser`) — wymaga osobnej decyzji architektonicznej, powiązane z #12.
- **#9** (lokalny skrypt LLM do generowania opisów) — osobne narzędzie CLI, nie dotyczy UI aplikacji.
- **#12** (uprawnienia) — pominięte na życzenie użytkownika (świadomy stan testowy).
- **#14** (`desktop.ini` w SVN) — dochodzenie/higiena repo SVN, nie zmiana kodu aplikacji; brak hooków SVN w repo do analizy.
- **#19** (obsługa `.kicad_dbl`) ✅ **WDROŻONE** (2026-09-17) — patrz sekcja #2+#3+#19 wyżej. Potwierdzone badaniem kodu źródłowego KiCada, że Symbol/Footprint Library Table faktycznie na żywo czyta pliki `.SchLib`/`.PcbLib` (od KiCad 7/8, `Type=Altium`, tylko do odczytu, konwersja w pamięci, zero nowych plików na dysku) — więc rozwiązanie działa bez zmiany formatu bibliotek źródłowych, zgodnie z wymaganiem użytkownika.

---

## Rekomendowana kolejność PR-ów

1. #17 + #16 + #15 (jeden plik `ElementForm.vue`, wspólny kontekst layoutu)
2. #8 — ESC workaround + zgłoszenie blockera nawigacji do repo `onyks-web-ui-system`
3. #6 + #13 (frontend + backend `/element/list`, razem)
4. #11 (full-width toggle)
5. #10 — odkomentowanie karty Dashboard + osobny follow-up backendowy (SVN hooks)
6. #2 + #3 (Settings + .DbLib) — z review bezpieczeństwa
7. #4 + #18 (wspólna migracja DB; #18 ew. tylko UI-ready, do jawnego uzgodnienia)

**Zamknąć bez zmian kodu:** #7, #5 (potwierdzone przez użytkownika jako już rozwiązane).

## Weryfikacja

- Frontend: `cd frontend && npm run dev`, ręczne przejście przez każdy zmieniony widok (Management, Element add/edit/duplicate/details, Dashboard, nowy Settings) w przeglądarce, w tym test na wąskim oknie (sprawdzenie #6.2/#11).
- Backend: `cd backend && uvicorn main:app --reload` (lub przez `docker compose`), test nowych/zmienionych endpointów (`/element/list?search=...`, `/server/identity`, `/settings/dblib`) przez curl/Swagger UI (`/docs`).
- Po etapie 3: weryfikacja wygenerowanego `.DbLib` przez faktyczny import w Altium Designer (jeśli dostępny) oraz test `ALTER TABLE` na kopii bazy testowej przed produkcją.

## Pliki krytyczne
- `frontend/src/components/ElementForm.vue`
- `frontend/src/views/ManagementView.vue`
- `frontend/src/App.vue`
- `backend/main.py`
- `backend/models.py`

---

## Dziennik wdrożenia

### 2026-09-16 — Etap 1 (#17, #16, #8-ESC) + część Etapu 2 (#10-UI, #6, #13, #11)

Zweryfikowane przez przebudowę `frontend`+`backend`+`proxy` w Docker Compose (build bez błędów, `GET /` → 200, ręczne testy `curl` na `/api/element/list` z `search`/`tables`). Nieprzetestowane wizualnie w przeglądarce (brak dostępu do przeglądarki w tym środowisku) — do potwierdzenia przez użytkownika.

**Zmienione/nowe pliki:**
- `frontend/src/components/ElementForm.vue` — etykiety Symbol Reference/Path (#17), `v-if` na sekcjach Footprint 2/3 wg `footprint1Filled`/`symbolFilled`/`footprint2Filled` (#16)
- `frontend/src/views/ManagementView.vue` — etykiety kolumn (#17), pole wyszukiwania + `CategoryFilter` + przycisk "Expand/Collapse table" nad tabelą, `BasicButtonsPanel` przeniesiony pod tabelę (#6.2), persystencja filtrów w `localStorage` (#6.1, #13, #11)
- `frontend/src/components/RepositoryModelSelector.vue` — listener Escape zamykający dialog (#8, częściowo — nawigacja folderów nadal blokowana przez zewnętrzną bibliotekę)
- `frontend/src/views/DashboardView.vue` — odkomentowana karta "Repository statistics" z adnotacją o danych orientacyjnych (#10, część UI)
- `frontend/src/App.vue` — `provide`/`inject` `fullWidth`/`toggleFullWidth`, CSS `main.full-width` (#11)
- `frontend/src/components/CategoryFilter.vue` — **nowy** komponent filtra kategorii (Select all / Deselect all + checkboxy)
- `frontend/src/utils/storage.js` — **nowy** helper `readStorage`/`writeStorage` (bezpieczny wrapper na `localStorage`)
- `frontend/src/utils/api.js` — `element.list(limit, skip, search, tables)` — nowe opcjonalne parametry
- `backend/main.py` — `GET /element/list` przyjmuje teraz `search` (ILIKE po partName/manufacturer/description/value) i `tables` (comma-separated lista kategorii, filtr `IN`)

**Zamknięte bez zmian kodu (potwierdzone przez użytkownika):** #7, #5.

**Nowe ustalenie od użytkownika:** plik .DbLib (#3, Etap 3) ma być generowany w pełni dynamicznie z bieżącej listy tabel kategorii przy każdym pobraniu — patrz zaktualizowana sekcja #2+#3 powyżej.

**Pozostało z Etapu 2:** brak — Etap 2 w całości wdrożony.

### 2026-09-16 (cd.) — #15

`ElementForm.vue` przeprojektowany na osobne, tytułowane sekcje `onyks-card`: "Basic Information" (UUID/Part Name/Manufacturer/Value/Table/Availability/Created At/Description, rozdzielone `<hr>`), "Symbol", "Footprints" (footprint 1/2/3 w responsywnej pod-siatce, 1/2/3 kolumny zależnie od szerokości), "Suppliers", "Datasheet". Przy weryfikacji odkryto, że użyty początkowo `<onyks-divider>` **nie istnieje** w bibliotece `onyks-web-ui-system` (zweryfikowane przez zbudowanie build-stage obrazu Dockera i przegrep `node_modules/onyks-web-ui-system/dist/*.js` — pełna lista dostępnych custom elementów tam jest) — zastąpiono zwykłym `<hr>` stylowanym przez `var(--onyks-surface-1-border)`. Build zweryfikowany (`docker compose up --build frontend`, HTTP 200, brak błędów kompilacji). **Etap 2 planu w całości ukończony.**

### 2026-09-17 — korekta #15 na życzenie użytkownika (kompaktowy layout)

Pierwsza wersja #15 (osobne duże karty) nadal była zbyt rozłożysta — użytkownik poprosił o wersję bardziej kompaktową, mieszczącą się w większości na jednym ekranie bez przewijania, z konkretnym układem:
- pola tekstowe jednowierszowe (Part Name, Value, Availability, UUID/Created At) w jednym rzędzie na górze formularza,
- Description jako krótkie, zwarte pole pod spodem (zmniejszone z `rows="10"` na `rows="3"`, usunięto osobne linijki "Min./Max. characters" na rzecz atrybutu `maxlength`),
- lewa kolumna: Symbol + Footprinty (1/2/3) + Datasheet — footprinty w zwartych, jednowierszowych blokach (Reference + Path + przycisk Select w jednym rzędzie, bez osobnych etykiet nad każdym polem, tylko placeholder) zamiast rozbudowanych sekcji — bo w 99% przypadków będzie tylko Footprint 1, więc miejsce na 2/3 ma być minimalne (nadal `v-if` z #16, ale teraz zajmują tylko ~1 wiersz, nie cały blok),
- prawa kolumna: Manufacturer / Category / Suppliers ("tabelki" z `ValueSelector`/`SuppliersSelector`) w mniejszych kartach (`size="m"`).

Dodatkowo zmniejszono wysokość wewnętrznej listy `<onyks-select>` w `ValueSelector.vue` i `SuppliersSelector.vue` z `height: 300px` na `160px` (oba komponenty są używane wyłącznie w `ElementForm.vue`, więc zmiana jest bezpieczna projektowo). Build zweryfikowany ponownie (HTTP 200, brak błędów).

### 2026-09-17 (cd.) — korekta wyrównania wierszy Symbol/Footprint + Datasheet, powiększenie podpisów

Po zrzucie ekranu od użytkownika wykryto dwie przyczyny "krzywego" wyglądu:
1. **Wiersze Symbol/Footprint 1/2/3** — układ 3-kolumnowy (Reference + Path + przycisk Select) w wąskiej karcie obcinał tekst w polach, a przycisk "Select Footprint N" zawijał się do dwóch linii (dłuższy tekst), przez co wiersze miały różną wysokość. Naprawiono: pola Reference/Path są teraz w osobnym 2-kolumnowym rzędzie, a przycisk Select w pełni własnym, pełnej szerokości rzędzie pod spodem — każdy wiersz (Symbol, Footprint 1/2/3) ma teraz identyczny kształt (2 pola + 1 przycisk pod spodem), bez zawijania i obcinania tekstu.
2. **Sekcja Datasheet** — była złożona jako `type="grid" cols="2"` z `DatasheetPicker` jako jednym z elementów siatki, ale `DatasheetPicker.vue` renderuje WIELE korzeni (fragment: opcjonalne checkboxy + strefa przeciągania pliku + osobny przycisk Reset) — w Vue 3 taki komponent użyty bezpośrednio jako dziecko grida rozbija się na osobne, niezależne komórki siatki, przez co "Reset" i strefa uploadu lądowały w przypadkowych miejscach. Naprawiono przez zmianę na `type="stack"` i owinięcie `DatasheetPicker` w jego własny dedykowany kontener — teraz wszystkie jego elementy renderują się spójnie, jeden pod drugim.

**Powiększenie podpisów pól:** wszystkie etykiety pól (UUID, Part Name, Value, Availability, Created At, Description, Datasheet, "Selected: ...") zmienione z `size="s"` na `size="m"` w `ElementForm.vue`.

Build zweryfikowany ponownie (HTTP 200, brak błędów kompilacji).

### 2026-09-17 (cd.) — poszerzenie Part Name / Value

Pola Part Name i Value w górnym rzędzie dostały klasę `.field-wide` (`grid-column: span 2`, aktywną tylko gdy `width > 550` żeby nie psuć układu na wąskich ekranach z 1 kolumną) — zajmują teraz podwójną szerokość względem Availability/UUID/Created At. Przy okazji przeniesiono UUID za Availability w kolejności DOM, żeby w trybie "add"/"duplicate" Part Name+Value idealnie wypełniały cały pierwszy rząd siatki (4 kolumny → 2+2), a w trybie edit/details pozostałe pola spływają czysto do kolejnego rzędu. Build zweryfikowany (HTTP 200).
