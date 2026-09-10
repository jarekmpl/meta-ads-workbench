---
name: meta-ads-report
description: Przygotuj raport wyników wszystkich kampanii Meta Ads za wskazany okres na podstawie lokalnego silnika FB Manager. Używaj dla próśb o zestawienia, wyniki i raporty; audyt z diagnozą obsługuje meta-ads-audit. Obsługuje podłączone konta Meta oraz jawny tryb demo.
---

# Raport kampanii

Katalog projektu jest dwa poziomy powyżej tego pliku. Uruchamiaj jego lokalne `.venv/bin/meta-ads` albo zainstalowane `meta-ads` z katalogu projektu. [AGENTS.md](../../AGENTS.md) zawiera wspólne zasady doboru konta i okresu.

Najpierw sprawdź `meta-ads capabilities`. Jeżeli prośba dotyczy prawdziwego konta, a `sources.meta` jest `false`, powiedz, że silnik nie obsługuje raportowania Meta. Nie generuj jego raportu z danych syntetycznych.

## Przepływ

1. Rozpoznaj konto przez katalog `clients list` i `accounts list --client ID`. W trybie demo dodaj globalne `--demo`. Wykorzystaj jednoznaczny wybór z rozmowy; pytaj tylko o rzeczywistą niejednoznaczność. Nie zakładaj, że identyfikator konta jest identyfikatorem klienta.
2. Ustal dokładne daty i strefę konta. Dla Meta używaj poleceń bez `--demo`; katalog obejmuje tylko lokalnie skonfigurowane konta. Przy demonstracji „ostatnie N dni” odnieś do końca zestawu z `capabilities` i podaj rzeczywiste daty w odpowiedzi. Nie skracaj okresu bez poinformowania użytkownika.
3. Uruchom `sync` na całym wymaganym zakresie. Zapisz zwrócone `run_id` i sprawdź `ok` oraz `data.status`. To pozwala związać raport z konkretną wersją danych.
4. Uruchom `report campaigns` z tymi samymi datami i `--snapshot` wskazującym zapisany `run_id`. Komenda obejmuje wszystkie kampanie snapshotu, również wstrzymane i z innym celem.
5. Przedstaw tabelę kampanii i najważniejsze wyniki z JSON, z kontem, okresem i walutą. Cel, konwersje i koszt wyniku pokazuj osobno dla odpowiednich typów kampanii. `null` opisuj jako brak danych, a nie zero. Przy dużym raporcie zapisz pełny JSON przez `--output`, dołącz link, podaj liczbę wszystkich kampanii i jawnie oznacz skrót w rozmowie.

Przykład wykonawczy dla demonstracji raportu 30-dniowego:

```bash
meta-ads --demo sync --client demo-shop --account act_DEMO_SHOP --last-days 30
meta-ads --demo report campaigns --client demo-shop --account act_DEMO_SHOP --last-days 30 --snapshot SYNC_ID
```

Zastąp `SYNC_ID` identyfikatorem z wyniku pierwszej komendy. Do eksportu umieść `--output reports/UNIKALNA_NAZWA.json` przed `report`. Nie nadpisuj istniejącego artefaktu. Nie podawaj tych komend użytkownikowi zamiast wykonania jego prośby.

## Interpretacja i błędy

Definicje wskaźników i zasady porównywalności są w [kompendium: metryki i metody](../../knowledge/meta-ads/metrics-and-methods.md). Korzystaj z nich przy interpretacji raportu; opis planowanej metody nie oznacza gotowej funkcji silnika. Szersze diagnozy i rekomendacje prowadź przez skill audytu oraz właściwe karty kompendium.

- Sumę wydatków bierz z `summary`. Wyniki biznesowe są pogrupowane w `goal_groups`; nie obliczaj jednego CPA dla leadów i zakupów.
- `measurement_status: unmapped` oznacza brak przypisania celu. Kampania nadal pozostaje w raporcie; nie przypisuj jej arbitralnie do e-commerce lub leadów.
- `INSUFFICIENT_DATA`: jeśli źródło ma wymagany okres, pobierz go i ponów raport na nowym snapshotcie. Jeśli źródło go nie ma, wskaż dostępne daty; nie udawaj pełnego wyniku.
- Przy pytaniu o kilka kont wykonaj odczyty osobno. Pokaż błędy kont, których nie udało się odczytać, i wyniki pozostałych. Nie sumuj różnych walut.
- Status kampanii jest stanem przy pobraniu, a nie dowodem sposobu emisji w całym analizowanym okresie.
- Ten skill przedstawia wyniki. Rekomendacje szerszych zmian wymagają procedury [audytu](../meta-ads-audit/SKILL.md).

## Dane Meta

`sync` pobiera strony listy kampanii i dzienne Insights oraz uzgadnia sumy emisji z kontem. `RECONCILIATION_FAILED`, `INCOMPLETE_DATA`, `RATE_LIMITED` i błędy autoryzacji oznaczają brak nowego kompletnego snapshotu. Nie używaj wtedy starego raportu jako aktualnego. Przy błędzie porównania można raz ponowić odczyt; jeśli nie pomoże, przedstaw ograniczenie.

- `objective` pochodzi z kampanii Meta. `goal_type: null` oznacza brak mapowania celu biznesowego, a nie błąd ustawień kampanii.
- `reported_actions` i `reported_action_values` pokazuj osobno dla każdego typu zdarzenia. Nie sumuj aliasów, np. `lead` i `onsite_conversion.lead_grouped`, jako osobnych leadów. Brak mapowania uniemożliwia ocenę CPL/CPA/ROAS.
- `days_without_insight_row` oznacza dni uzupełnione zerami emisji po pełnym pobraniu; nie dowodzi poprawności pomiaru konwersji.
- Jeśli nie było wydatków, powiedz to wprost. Nie twórz rankingu efektywności z zer ani nie sugeruj automatycznie awarii konta.
- Atrybucja raportów Meta to jawne 7 dni po kliknięciu i 1 dzień po wyświetleniu. Porównanie z panelem wymaga zgodnych dat i ustawień.

## Redakcja przed przekazaniem

Stosuj [standard rekomendacji i języka analiz](../../docs/analysis-standard.md) do komentarzy: konkretne fakty, bez ogólnych zastrzeżeń i przytaczania wewnętrznych wytycznych. Samo zestawienie liczb zachowuje zakres zamówiony przez użytkownika.

Każdy raport i jego podsumowanie poddaj redakcji [miodkuj](../miodkuj/SKILL.md) w trybie Embedded or file mode. Zastosuj [zasady projektu](../../AGENTS.md#redakcja-raportów-po-polsku), w tym końcową kontrolę `references/eval.md` i zapis kontroli dla raportu w pliku. Zachowaj obliczenia, zakres i definicje wskaźników. Przekaż tekst po korekcie; nie zastępuj raportu listą uwag językowych.

## Eksport do PDF

Jeżeli użytkownik chce dokument, wykonaj [meta-ads-pdf](../meta-ads-pdf/SKILL.md) na zapisanym raporcie. Komentarz agenta można dołączyć jako osobny `pdf_notes`; nie zmieniaj źródłowych obliczeń.
