---
name: meta-ads-update
description: Aktualizuj zainstalowaną przestrzeń Meta Ads Workbench z wydania GitHub lub lokalnej paczki, zachowując dane klientów, kontekst i profil specjalisty. Użyj przy sprawdzeniu wersji, aktualizacji lub odzyskaniu instalacji po przerwanym wdrożeniu.
---

# Aktualizacja przestrzeni klienta

Przeczytaj [instrukcję aktualizacji](../../docs/updating.md). To praca nad lokalnym narzędziem, bez zmian w Meta. Nie wykonuj git pull w katalogu klienta, kopiowania całej paczki na istniejący katalog ani reinstalacji przez install.py.

Ustal właściwy katalog z `workspace.json`. Zakończ inne operacje tej przestrzeni. W instalacjach sprzed 0.6 starsze procesy nie obsługują blokady aktualizacji, więc nie uruchamiaj migracji równolegle z ich pracą. Osobisty profil może być wspólny dla kilku klientów; aktualizator go nie otwiera ani nie zmienia.

Najpierw wykonaj podgląd `python3 update.py --github` albo `--source ...`. W starszej instalacji uruchom update.py z rozpakowanego nowego wydania i podaj `--workspace`. Pobieranie przez `--github` automatycznie pobiera także oryginalną paczkę bazową, jeśli jest potrzebna. Korzystaj wyłącznie z przewidzianego repozytorium i opublikowanych wydań. Tokenów GitHuba nie przyjmuj w rozmowie; użyj istniejącej autoryzacji gh.

Sprawdź wersję docelową, listę plików i konflikty. Jeśli użytkownik polecił aktualizację, a podgląd nie ma konfliktów, wykonaj `--apply` z tą samą jawną wersją `--version vX.Y.Z`. Nie żądaj osobnej zgody na ten sam zakres. Przy prośbie jedynie o sprawdzenie dostępności zakończ na podglądzie.

Konflikt oznacza lokalną zmianę pliku narzędzia albo kolizję z własnym plikiem. Przeczytaj konkretną różnicę. Własną wytyczną przenieś do profilu, a materiał klienta do kontekstu, zachowując oryginał w kopii. Nie resetuj plików, nie usuwaj blokady i nie dopisuj zmienionych hashy do installed.json. Zmianę kodu wymagającą utrzymania opracuj w repozytorium narzędzia; nie maskuj jej jako wytycznej.

Po powodzeniu uruchom `python3 workbench.py doctor`, `python3 workbench.py meta capabilities` i `python3 workbench.py specialist list`. Sprawdź wersję oraz dostępność danych przez zwykłe lokalne komendy. Zrestartuj rozmowę lub przeładuj AGENTS.md i właściwe skille. Nie korzystaj ze starego `.venv/bin/meta-ads` po aktualizacji; workbench.py wybiera aktywne środowisko.

Jeśli aktualizator sam odtworzył poprzednią wersję, sprawdź ją i usuń przyczynę błędu przed kolejną próbą. Przy przerwaniu procesu użyj `python3 update.py --workspace ... --rollback` z kompletnej paczki poza klientem. Jeśli odtworzenie wykrywa późniejszą ręczną zmianę, zachowaj ją i rozwiąż konkretny konflikt. Nie kasuj pending.json ani kopii, aby wymusić start.

Zakończ informacją o wersji, wyniku kontroli i ewentualnej nierozwiązanej przeszkodzie. Nie obiecuj harmonogramu ani automatycznych aktualizacji w tle.
