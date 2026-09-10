# Raporty PDF Bluerank

PDF jest warstwą prezentacji nad zapisanymi wynikami. Ten sam generator Python działa z dowolnym agentem mającym dostęp do plików i terminala. Procedura agenta: [meta-ads-pdf](../skills/meta-ads-pdf/SKILL.md).

Przed eksportem agent sprawdza język całego dokumentu za pomocą [miodkuj](../skills/miodkuj/SKILL.md), zgodnie z [zasadami projektu](../AGENTS.md#redakcja-raportów-po-polsku). Korekta zachowuje liczby, definicje metryk i ograniczenia analizy. Zapis `language-review.json` dotyczy sprawdzonej wersji tekstu; kontrola wyglądu PDF następuje po redakcji. Generator Python sam nie ocenia naturalności języka.

Możesz powiedzieć: „Zapisz ten audyt do PDF”, „Przygotuj raport Bluerank ze wszystkich kampanii” albo „Dodaj rekomendacje z naszej analizy do dokumentu dla klienta”. Agent rozpoznaje źródło, przygotowuje dokument i sprawdza jego wygląd.

## Instalacja i wykonanie

```bash
uv sync --locked --python 3.11 --extra pdf
.venv/bin/meta-ads pdf export --client example-client --account act_EXAMPLE --input examples/pdf/analysis.json --pdf output/pdf/przyklad-analizy.pdf
.venv/bin/meta-ads pdf render --pdf output/pdf/przyklad-analizy.pdf --directory tmp/pdfs/przyklad-analizy
```

`reportlab` składa dokument, `pypdf` kontroluje czytelność tekstu i liczbę stron, `pypdfium2` renderuje podglądy. Nie jest wymagany systemowy Poppler. Fonty z polskimi znakami i logotyp są dołączone do pakietu. Bez `uv` użyj `pip install -e '.[pdf]'`; ta ścieżka nie używa lockfile.

Nie dodawaj flagi `--demo` do `pdf`. Źródło pochodzi z pliku. `--pdf` wskazuje dokument wynikowy, a globalne `--output` służy do zapisania odpowiedzi JSON komendy. Eksport nie potrzebuje poświadczeń Meta.

## Trzy ścieżki treści

| Wejście | Zastosowanie | Efekt |
| --- | --- | --- |
| `campaign_report`, `account_audit`, `analysis_report` | Zapisany JSON silnika lub poprawna koperta CLI | Automatycznie dobrane sekcje, pełna lista kampanii, podstawowe wyniki, cele, ograniczenia i dowody |
| Raport oraz `--notes` z `pdf_notes` | Wnioski agenta lub specjalisty obok obliczeń | Komentarz na początku dokumentu, zgodność klienta, konta, raportu i snapshotu |
| `pdf_document` | Inne, indywidualnie opracowane analizy | Tytuł, podsumowanie, KPI, sekcje tekstowe, listy i tabele według jawnej struktury |

Schematy: [pdf_document](../schemas/pdf_document.schema.json), [pdf_notes](../schemas/pdf_notes.schema.json). Przykłady: [analiza](../examples/pdf/analysis.json), [komentarz](../examples/pdf/notes.json). Identyfikatory komentarza są przykładowe: przed eksportem zastąp je rzeczywistymi ID źródłowego raportu. Komentarz nie może dotyczyć innego snapshotu.

`pdf_document` nie pobiera ani nie weryfikuje danych biznesowych. Pole `source` jest deklaracją autora; przy opracowaniach ręcznych stosuj `manual`, przy danych demonstracyjnych `demo`. Generator sprawdza zgodność pól klienta i konta, ale nie stanowi mechanizmu autoryzacji dostępu do samodzielnie dostarczonego pliku.

Sekcja zawiera `title` oraz opcjonalne `paragraphs`, `bullets`, `table`, `new_page`. Tabela ma 1-6 kolumn, wiersze o identycznej liczbie komórek, opcjonalne względne `widths` i indeksy `numeric_columns` liczone od zera. Tekst jest escapowany: tagi HTML, ścieżki do obrazów i Markdown nie wykonują żadnych operacji ani nie formatują treści. Szerokie analizy rozbijaj na kilka tabel. Limity chronią przed przypadkowo ogromnymi dokumentami; błąd walidacji nie powoduje cichego przycięcia danych.

## Układ

- A4, stałe marginesy, logo Bluerank na każdej stronie, zachowane proporcje.
- Ciemny tekst, białe tło i akcent `#38B4E7` zaczerpnięty z dostarczonego logo.
- Czytelna hierarchia tytułów, karty najważniejszych liczb, dyskretne pasy w tabelach.
- Powtarzane nagłówki tabel i stopka ze źródłem, datą raportu oraz numerem strony.
- Osadzone fonty DejaVu Sans; źródło i licencja w `src/meta_ads_manager/assets/fonts/`.

Szablon ma wersję `bluerank-1.0`. Nie dodaje wykresów, ocen skuteczności ani rekomendacji, których nie ma w treści. Nietypowe znaki bez glifu pokazuje jako `[U+…]` i wymienia w metadanych oraz przypisie. Zwykłe polskie litery są obsługiwane. Pełny JSON pozostaje źródłem dokładnych wartości; PDF formatuje liczby dla odbiorcy.

## Kontrola i przekazanie

1. Sprawdź źródło, klienta, konto, okres, walutę, ograniczenia i kompletność kampanii.
2. Eksportuj do nowej nazwy w `output/pdf/`. Generator nie nadpisuje PDF ani jego manifestu.
3. Przeczytaj wynik: liczba stron, lista znaków zastępczych, ścieżki i sumy SHA-256.
4. Renderuj do nowego katalogu w `tmp/pdfs/` i obejrzyj **każdą stronę**. Kontrola tekstowa nie wykrywa ucięcia kolumn ani złego układu.
5. Popraw problemy, ponów eksport i kontrolę. Zachowaj notatkę z nazwą i hashem PDF, numerami obejrzanych stron, datą i wynikiem kontroli.
6. Przekaż finalny PDF; zachowaj źródłowy JSON, ewentualny komentarz i manifest do odtworzenia.

Manifest `.pdf.json` zapisuje wersję szablonu, zakres, źródło, liczbę stron, czas wygenerowania i hashe PDF oraz wejść. `automated_checks: passed` oznacza przejście kontroli technicznych. `visual_review: required` jest przypomnieniem; generator nie twierdzi, że człowiek lub agent obejrzał strony. Pliki PDF i manifesty mają uprawnienia `0600`; katalogi `output/` i `tmp/` są ignorowane przez Git. Wyniki mogą zawierać dane klientów i nie należą do dystrybucji kodu.

## Obsługa błędów

| Kod | Działanie |
| --- | --- |
| `PDF_DEPENDENCY` | Zainstaluj dodatek `pdf` |
| `SCOPE_MISMATCH` | Sprawdź klienta, konto oraz powiązanie komentarza; nie przepisuj ID tylko po to, aby ominąć błąd |
| `OUTPUT_EXISTS` | Wybierz kolejną wersję nazwy lub katalogu podglądu |
| `PDF_INPUT` / `VALIDATION_ERROR` | Popraw strukturę, wersję lub kompletność pliku; nie eksportuj nieudanego raportu |
| `PDF_LAYOUT` | Podziel zbyt duży blok lub tabelę, zachowując wszystkie dane |
| `PDF_VALIDATION` | Zbadaj dokument; nie przekazuj go jako gotowego |

Podgląd obsługuje 1-200 stron i 72-200 DPI. Zwykle wystarcza 110 DPI. Dokumenty większe podziel według logicznego zakresu. Aktualny proces nie wysyła dokumentów e-mailem, nie publikuje ich i nie wykonuje zmian w Meta.

## Cele i historia decyzji od wersji 0.3

[Proces celów i rekomendacji](goals-and-recommendations.md) opisuje trwałe definicje wyników, przypisania kampanii, terminy oraz ocenę testów. Przed kolejną analizą agent odczytuje te ustalenia przez skill meta-ads-decisions. Raporty Meta dołączają obliczenia i historię z chwili tworzenia; eksport PDF uwzględnia oba elementy. Rejestr pozostaje w przestrzeni klienta i wymaga kopii razem z danymi.
