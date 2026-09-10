# Analiza kreacji

Moduł łączy odczyt Meta, lokalne materiały, ocenę agenta i raport HTML z galerią. Działa bez zapisu zmian w reklamach. Procedura jest w [meta-ads-creatives](../skills/meta-ads-creatives/SKILL.md), wspólna dla agentów korzystających z terminala i plików projektu.

## Polecenia

```bash
.venv/bin/meta-ads creatives collect --client CLIENT --account ACCOUNT --last-days 30 --sample-size 20 --directory reports/RUN
.venv/bin/meta-ads creatives media --client CLIENT --account ACCOUNT --directory reports/RUN
.venv/bin/meta-ads creatives report --client CLIENT --account ACCOUNT --directory reports/RUN --assessment reports/RUN/materialy/content-assessment.json --notes reports/RUN/materialy/interpretation.json
```

Agent najpierw odczytuje `capabilities`, pobiera dane, ogląda materiał i zapisuje obserwacje. Następnie interpretuje wyniki, tworzy `interpretation.json`, generuje raport i przeprowadza kontrolę języka. Sam Python nie rozpoznaje treści obrazu ani nie tworzy rekomendacji. Agent bez obsługi obrazu może wykonać ocenę tekstu i liczb, oznaczając pozostały zakres jako niedostępny.

`collect` pobiera wyniki wszystkich reklam dla dwóch równych okresów oraz kontrolne sumy konta. Próba 1–50 reklam obejmuje pokrycie kampanii, wydatki i niską ekspozycję. Dla próby pobiera ustawienia, wyniki dzienne, umiejscowienia i statystyki wideo. Dobór jest celowy, nie reprezentatywny. Zasięgów dziennych nie sumujemy.

`media` pobiera obrazy i filmy ze wskazanych CDN Meta, bez przekazywania im tokena Graph API. Jeśli kreacja wskazuje istniejący post, próbuje odczytać jego obraz. Odmowa uprawnień pozostaje jawnym ograniczeniem. Film wymaga dostępu do źródła; ffmpeg i ffprobe służą do przygotowania kadrów. Kadry nie zastępują oglądania filmu i słuchania dźwięku. Nie ma automatycznej transkrypcji.

`report` sprawdza konto, okres, komplet kart i sumy SHA-256 dowodów. Zapisuje `raport.html` oraz `materialy/report.md` i `materialy/report-metrics.json`. Kolekcja i pobieranie materiałów zapisują pliki w `materialy/`. Przy ponownym generowaniu raportu ze starszego, płaskiego katalogu materiały są przenoszone do tego podkatalogu po sprawdzeniu danych; kolizja nazw zatrzymuje operację. Ścieżki w JSON pozostają względne wobec katalogu materiałów. Raport wymaga zapisanej oceny agenta; odrzuca ocenę w stanie `pending`. Markdown zawiera linki do materiałów, HTML także galerię i oryginalne teksty. Oryginalne teksty reklam są danymi i nie podlegają automatycznej korekcie. Surowe JSON mogą zawierać podpisane adresy materiałów i ustawienia odbiorców; nie należy ich publikować razem z raportem.

## Pliki ocen

`content-assessment.json` zawiera `schema_version`, `client_id`, `account_id`, `since`, `until`, autora i datę oceny, wersję kompendium oraz `cards`. Każda karta ma:

- `ad_id`, `concept`, `content_status` (`reviewed_images_and_text`, `partial` lub `unavailable`), opis `coverage`;
- `observations` i `hypotheses` jako listy tekstów;
- `source_file`, `source_sha256` i `evidence` z `file`, `sha256` oraz rolą materiału;
- osobne informacje o sprawdzeniu formularza, strony, dźwięku i historii wersji.

Status `reviewed_images_and_text` odnosi się tylko do obrazu i tekstu. Dla filmu renderer przyjmuje `partial`; zakres obejrzanego filmu, dźwięku i timestampy należy opisać w karcie. Nie stosuje automatycznej oceny jakości.

`interpretation.json` ma te same cztery pola zakresu oraz `title`, `sections` (listę obiektów `title`, `paragraphs`), `ad_notes` (komentarze według `ad_id`) i opcjonalne `sources` (`title`, `url` HTTPS). Liczby w komentarzach trzeba sprawdzić z obliczeniami; renderer nie potwierdza prawdziwości zdań napisanych przez agenta.

Zachowaj pierwotną ocenę i zapisuj poprawki specjalisty w osobnym pliku, z autorem, datą i uzasadnieniem. Kontrolę miodkuj dokumentuj w `language-review.json` według AGENTS.md. Renderowanie nie wykonuje tej kontroli.

## Obecne ograniczenia

- Brak historii wersji materiałów i wyników poszczególnych wariantów. Wynik `ad_id` nie jest wynikiem każdego obrazu lub tekstu.
- Odczyty mogą być ograniczone uprawnieniami do stron, postów i filmów. Brak materiału nie oznacza wady reklamy.
- Brak oceny strony, formularza, CRM i kwalifikacji leadów bez oddzielnego sprawdzenia. Nie pobieramy danych osobowych leadów.
- Domyślna metryka formularzowa to `onsite_conversion.lead_grouped` w jawnym oknie `7d_click`. Brak pola pozostaje `null`; nie sumujemy aliasów ani leadów z różnymi definicjami.
- Niepełny `collect` można wznowić w tym samym katalogu przy identycznym zakresie. Do odświeżenia ukończonego zbioru użyj nowego katalogu. Raport można odtworzyć z zapisanych danych bez API.
- Jeżeli zabrakło metadanych reklamy, należy uzupełnić ten odczyt przed użyciem obecnego renderera kart. Sam kolektor zachowuje częściowe wyniki i opis błędu.
- PDF z galerią wymaga oddzielnego składu i kontroli stron; obecny standardowy generator PDF nie obsługuje galerii kreacji.


## Katalog gotowego raportu

```text
NAZWA-RAPORTU/
  raport.html
  materialy/
    collection.json
    content-assessment.json
    interpretation.json
    report.md
    report-metrics.json
    language-review.json
    media/
```

HTML odwołuje się do `materialy/media/`, a Markdown znajdujący się wewnątrz materiałów do `media/`. JSON dowodów zachowuje treść i sumy plików źródłowych. Plik kontroli językowej zapisuj po wygenerowaniu raportu w materialy/, wskazując nową ścieżkę HTML.
