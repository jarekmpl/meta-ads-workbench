# Meta Ads Workbench

Paczka dla specjalisty, który pracuje z kontami Meta Ads przez rozmowę z Codex, Claude Code albo Antigravity. Zawiera instalator osobnych przestrzeni klientów, silnik Python, skille analityczne, kompendium i eksport PDF z identyfikacją Bluerank.

**Zacznij od [START-HERE.md](START-HERE.md).** Instalacja prowadzi operatora krok po kroku:

```bash
python3 install.py
```

Wymagany jest Python 3.11+ oraz macOS, Linux lub WSL. Instalator tworzy odrębne środowisko klienta i instaluje przypięte zależności. Nie kopiuje danych z innych instalacji. Aplikację LLM wybierasz samodzielnie; musi mieć dostęp do plików i terminala.

## Co działa

- Instalacja przestrzeni jednego klienta, diagnostyka lokalna i kreator konfiguracji Meta.
- Rejestr dowolnych materiałów kontekstowych z zakresem projektu, statusami, datą ważności i kontrolą integralności.
- Odczyt skonfigurowanego konta, kampanii i dziennych wyników; raporty ze snapshotów, częściowy audyt i pilotaż analizy kreacji.
- Procedury agenta do interpretacji danych, rekomendacji, przeglądania materiałów i redakcji po polsku z miodkuj.
- Eksport raportów, audytów i własnych opracowań do PDF Bluerank oraz renderowanie do kontroli stron.
- Osobne bazy, konfiguracje, poświadczenia i raporty klientów. CLI wykrywa niezgodny zakres i ścieżki w zainstalowanych przestrzeniach.

## Co wymaga dalszego wdrożenia

Silnik obsługuje **wyłącznie odczyt Meta**. Nie tworzy kampanii ani nie zmienia budżetów i statusów. Proces nowej kampanii i nazewnictwo są opisane jako projekt, nie działający generator. Automatyczne mapowanie konwersji oraz analiza CPL/CPA/ROAS na rzeczywistych kontach wymagają dalszej implementacji; agent może pracować na jawnie ustalonych definicjach i sprawdzonych obliczeniach.

Analiza obrazu i interpretacja należą do agenta, nie do samego Pythona. Dostęp do formularzy, postów, filmów i pomiaru zależy od udostępnionych zasobów. `capabilities` oraz zakres danych w wyniku określają faktycznie dostępne funkcje.

## Zasady kont

Nigdy niczego nie kasujemy z konta. Każda przyszła zmiana, także utworzenie wstrzymanej kampanii, wymaga wyraźnej akceptacji konkretnego planu. Analiza, zgoda na instalację ani potwierdzenie kontekstu nie są zgodą na zapis. [Polityka zmian](docs/account-change-policy.md).

## Praca specjalisty

Każdy klient otrzymuje osobny katalog **poza repozytorium instalatora** i osobny projekt agenta. Kontekst, strategie, notatki oraz raporty pozostają prywatne. Nie otwieraj folderu wszystkich klientów jako jednego projektu. [Codzienny proces](docs/operator-workflow.md) opisuje start sesji, aktualizowanie ustaleń, pracę na kilku projektach, kopie zapasowe i granice izolacji.

Przykładowe polecenia w rozmowie:

> Pokaż raport ze wszystkich kampanii tego konta za ostatnie 30 pełnych dni.

> Uwzględnij strategię tego projektu i zaproponuj najważniejsze testy.

> Dodaj te ustalenia ze spotkania do kontekstu jesiennej promocji.

> Zapisz całą analizę w PDF.

## Dokumentacja

| Dokument | Do czego służy |
| --- | --- |
| [Start operatora](START-HERE.md) | Instalacja, wybór agenta, połączenie i pierwszy wynik |
| [Codzienna praca](docs/operator-workflow.md) | Separacja klientów i otwarty rejestr kontekstu |
| [Konfiguracja Meta](docs/meta-setup.md) | Aplikacja, lokalne poświadczenia i test odczytu |
| [Instrukcje agenta](AGENTS.md) | Wybór skilli, zasady danych i redakcja |
| [Kompendium](knowledge/meta-ads/README.md) | Zasady analiz i planowania testów |
| [PDF](docs/pdf-export.md) | Skład dokumentów i kontrola stron |
| [Kreacje](docs/creative-analysis.md) | Materiały, ocena agenta i raport |
| [Proces nowej kampanii](docs/campaign-planning-process.md) | Specyfikacja przyszłego procesu |
| [Nazwy kampanii](docs/campaign-naming-standard.md) | Proponowany standard struktury i nazw |
| [Wydawanie paczki](docs/releasing.md) | Jawny wykaz plików, kontrola i publikacja |

## Rozwój i testy

W katalogu kodu, poza klientami:

```bash
uv sync --locked --python 3.11 --extra pdf
uv run --locked pytest -q
uv run --locked ruff check src tests install.py workbench.py package_release.py
python3 package_release.py --check
```

Demo jest oddzielne od kont klientów i używa stałego okresu syntetycznych danych. [Instrukcja demo](docs/demo-guide.md).

Repozytorium i ZIP powstają z `release-files.json`. Raporty, dane kont, prywatne konfiguracje, kontekst klientów, poświadczenia i lokalne recenzje plików nie są częścią paczki. Miodkuj i fonty zachowują swoje licencje; [zasady dystrybucji](DISTRIBUTION.md) opisują dołączone zasoby.
