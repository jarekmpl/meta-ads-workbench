# Kontrakt CLI v0.1

Opisuje docelowy interfejs. **Działający podzbiór v0.1** i dokładną składnię opisuje [instrukcja demo](demo-guide.md). Dostępne są `capabilities`, `clients list`, `accounts list`, `sync`, `sync status`, `analyze`, `report campaigns`, `report show`, `audit`, `validate` i `schema export`. Bez `--demo` działa odczyt skonfigurowanych kont Meta (szczegóły w [instrukcji Meta](meta-setup.md)); `--demo` wybiera dane syntetyczne. Od wersji 0.3 `analyze` działa także dla Meta po jawnym przypisaniu celu. Dostępne są również `goals` i `recommendations`; dokładną składnię i nowe kontrakty opisuje [proces celów i decyzji](goals-and-recommendations.md). `--output` i `--format` także występują przed nazwą polecenia. Od wersji 0.4 działa także rodzina `wizard`; składnię i granice opisuje [kreator kampanii](campaign-wizard.md). Pozostałe komendy poniżej są planowane.

## Konwencje

Dostępne są również `auth init`, `auth status`, `auth store-token` i `auth check` opisane w [konfiguracji Meta](meta-setup.md). Te polecenia nie używają `--demo`. W obecnej fazie `auth check --client ID` sprawdza jedno konto jawnie zapisane w lokalnej konfiguracji klienta; nie przyjmuje jeszcze flagi `--account` ani `--capability` z docelowych przykładów niżej.

Nazwa komendy: `meta-ads`. Każda operacja dotycząca konkretnego konta wymaga `--client` i `--account`, także gdy plan zawiera te pola. Wartości muszą być zgodne. Nie ma domyślnego „ostatniego konta”.

Listowanie klientów nie wymaga konta. Listowanie kont wymaga klienta. Dane z API muszą przejść sprawdzenie zakresu przed odczytem lub zapisem.

Domyślny wynik maszynowy to jeden dokument JSON na stdout. Komunikaty postępu trafiają na stderr. `--format text` służy użytkownikowi, a `--output` zapisuje artefakt. Tokeny nie są obsługiwane jako argumenty CLI. `--help` nie wymaga połączenia z API.

Każda odpowiedź zawiera `schema_version`, `request_id`, `ok`, `data`, `warnings`, `error`. Ostrzeżenia są obiektami z kodem i opisem. Błąd zawiera `code`, `message`, `retryable` i bezpieczne szczegóły; bez sekretów i surowych requestów.

```json
{
  "schema_version": "1.0",
  "request_id": "req_example",
  "ok": true,
  "data": {"run_id": "sync_example", "status": "SUCCEEDED"},
  "warnings": [],
  "error": null
}
```

## Polecenia

Poniższy zakres `--client demo --account act_DEMO` jest przykładowy i nie wskazuje prawdziwego konta.

```bash
meta-ads clients list
meta-ads accounts list --client demo
meta-ads auth check --client demo --account act_DEMO --capability read
meta-ads auth check --client demo --account act_DEMO --capability create-campaign

meta-ads sync --client demo --account act_DEMO --last-days 90
meta-ads sync status --client demo --account act_DEMO --run sync_example
meta-ads sync --client demo --account act_DEMO --since 2026-08-01 --until 2026-08-31

meta-ads analyze --client demo --account act_DEMO --recipe weekly-review --goal leads-pl
meta-ads report show --client demo --account act_DEMO --run analysis_example

meta-ads campaign plan --client demo --account act_DEMO --brief brief.json --output proposal.json
meta-ads changes validate --client demo --account act_DEMO --proposal proposal.json --output plan.json
meta-ads changes show --client demo --account act_DEMO --plan plan.json
meta-ads changes authorize --client demo --account act_DEMO --plan plan.json
meta-ads changes apply --client demo --account act_DEMO --plan plan.json
meta-ads changes status --client demo --account act_DEMO --execution exec_example
meta-ads changes reconcile --client demo --account act_DEMO --execution exec_example
```

`sync` domyślnie czeka na wynik do skonfigurowanego timeoutu. `--no-wait` zwraca identyfikator zadania; akceptacja zadania nie oznacza ukończonej synchronizacji. Proces/worker umożliwiający kontynuację po wyjściu CLI musi istnieć przed udostępnieniem tego wariantu.

`analyze` korzysta z zapisanych danych, sprawdza ich aktualność i zwraca `INSUFFICIENT_DATA`, gdy warunki procedury nie są spełnione. Wynik obejmuje metryki, dowody, ograniczenia i kandydatów na rekomendacje. LLM może opracować ich interpretację, ale nie podmienia obliczonych wartości.

`campaign plan` tworzy lokalną propozycję; nie zapisuje nic w Mecie. Brak zasobu lub pola zwraca `missing_requirements`. `changes validate` wykonuje odczyty i tworzy plan dopiero po pełnej walidacji. Walidacja jest lokalna oraz, tam gdzie obsługiwane, po stronie API; nie gwarantuje późniejszego zatwierdzenia reklam przez Metę.

`changes authorize` pokazuje konkretne konto, wartości przed/po, zakres i ważność, a następnie wymaga interaktywnego potwierdzenia. Tryb bez interakcji nie może sam wystawić upoważnienia. Polityka automatyzacji nie upoważnia do zapisu. Każda zmiana wymaga akceptacji użytkownika dla konkretnego planu zgodnie z [zasadami zmian na kontach](account-change-policy.md). `apply` nie pyta ponownie, gdy istnieje ważne upoważnienie obejmujące niezmieniony plan.

## Propozycja i wykonywalny plan

[Przykład propozycji](../examples/change-proposal.json) zawiera operację domenową, nie dowolny endpoint HTTP. Docelowy MVP ma wspierać zamknięty katalog operacji: tworzenie obsługiwanych kampanii/zestawów/reklam/kreacji, zmianę budżetu i zmianę statusu. Nie ma polecenia dowolnego zapisu do Graph API. Usuwanie obiektów, także przez status `DELETED`, jest bezwarunkowo zabronione, również w przyszłych wersjach wykonawcy.

Propozycja zawiera `schema_version`, `kind`, zakres, cel, operacje, uzasadnienie i dowody. Każda operacja ma własny identyfikator, typ, obiekt i jawne wartości. Odwołania do nowo tworzonych obiektów używają identyfikatorów operacji, które walidator sprawdza jako graf bez cykli.

Wykonywalny plan dodatkowo zawiera wygenerowane przez system `plan_id`, `plan_hash`, `validated_at`, `expires_at`, `policy_version`, pełne warunki wstępne i mapowanie jednostek API. Hash obejmuje kanoniczny JSON treści wykonawczej, zakresu, warunków, polityki i ważności. Algorytm kanonizacji oraz wersja schematu są częścią kontraktu. `plan_hash` nie jest dowodem zgody; upoważnienie jest odrębnym rekordem.

Operacje wykonawcy: `PENDING → RUNNING → VERIFIED`, albo `FAILED`/`UNKNOWN`. Całe wykonanie: `PENDING`, `RUNNING`, `SUCCEEDED`, `PARTIAL`, `FAILED`, `UNKNOWN`. `UNKNOWN` wymaga uzgodnienia, a nie automatycznego powtórzenia. `PARTIAL` oznacza, że część zapisów została wykonana; odpowiedź wskazuje wyniki poszczególnych operacji.

Pliki wejściowe mają wersję schematu, odrzucają nieznane pola i przechodzą walidację typów. Nie zawierają poleceń powłoki do wykonania. `kind: change_proposal` nie może zostać przekazane bezpośrednio do `apply`.

## Kody wyjścia

| Kod | Kategoria | Przykładowe kody błędów |
| --- | --- | --- |
| 0 | Polecenie wykonane lub zadanie przyjęte | Wynik zadania określa `data.status` |
| 2 | Niepoprawne wejście | `VALIDATION_ERROR`, `UNSUPPORTED_OPERATION` |
| 3 | Dostęp lub zakres | `AUTH_REQUIRED`, `PERMISSION_DENIED`, `SCOPE_MISMATCH` |
| 4 | Stan, polityka lub upoważnienie | `STATE_CONFLICT`, `PLAN_EXPIRED`, `POLICY_DENIED`, `AUTHORIZATION_REQUIRED` |
| 5 | Błąd zewnętrzny lub niepełne wykonanie | `RATE_LIMITED`, `API_ERROR`, `PARTIAL_EXECUTION`, `UNKNOWN_OUTCOME` |
| 6 | Brak danych do analizy | `INSUFFICIENT_DATA`, `INCOMPATIBLE_REPORTS` |
| 1 | Nieoczekiwany błąd wewnętrzny | `INTERNAL_ERROR` |

Polecenie `status` może zakończyć się kodem 0 i zwrócić wykonanie o stanie `FAILED`: udał się odczyt statusu. Polecenie `apply` kończące się częściowym wykonaniem zwraca kod 5, `ok: false` i szczegóły wykonania w `data`. Agent zawsze sprawdza zarówno kod wyjścia, jak i status domenowy.

## Eksport PDF

`pdf export --client ID --account ID --input RAPORT.json --pdf WYNIK.pdf [--notes KOMENTARZ.json]` tworzy dokument Bluerank i manifest. `pdf render --pdf WYNIK.pdf --directory KATALOG [--dpi 110]` tworzy PNG do obowiązkowego przeglądu wszystkich stron. Źródło pochodzi z pliku; nie dodawaj `--demo`. Wymagany dodatek `pdf`. Schematy `pdf_document` i `pdf_notes` są dostępne przez `schema export` i `validate`. Szczegóły: [proces PDF](pdf-export.md).
