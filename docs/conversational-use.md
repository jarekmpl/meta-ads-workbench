# Obsługa przez rozmowę

Użytkownik rozmawia z agentem LLM, który ma dostęp do tego repozytorium i terminala. Agent czyta instrukcje projektu, wybiera właściwy skill, uruchamia Python i przedstawia wynik. Nie jest potrzebny oddzielny model wbudowany w CLI ani parser polskich zdań w Pythonie.

Przepływ: prośba użytkownika → agent i skill → silnik Python → dane i obliczenia → szkic → redakcja miodkuj → odpowiedź lub dokument.

## Przykłady próśb

- „Pokaż raport ze wszystkich kampanii podłączonego klienta za ostatnie 30 dni”.
- „Zrób częściowy audyt podłączonego konta”.
- „Zrób audyt obu kont demonstracyjnych i wskaż, czym zająć się najpierw”.
- „Na podstawie tego raportu opisz kampanie, które nie spełniają celu”.
- „Wyjaśnij, skąd bierze się ten wniosek”.

Agent sam ustala identyfikatory z katalogu, pobiera dane i liczy przez CLI. Użytkownik otrzymuje tabelę, wnioski i link do pełnego raportu, jeśli jest potrzebny. Pytania doprecyzowujące dotyczą np. kilku kont o tej samej nazwie, nie doboru flag polecenia.

## Wspólne instrukcje

[AGENTS.md](../AGENTS.md) jest punktem wejścia i wskazuje skille:

- [Raport kampanii](../skills/meta-ads-report/SKILL.md).
- [Audyt konta](../skills/meta-ads-audit/SKILL.md).
- [PDF Bluerank](../skills/meta-ads-pdf/SKILL.md).
- [Miodkuj](../skills/miodkuj/SKILL.md), obowiązkowa redakcja raportów, analiz, audytów i podsumowań.

Plik [CLAUDE.md](../CLAUDE.md) odsyła do tej samej instrukcji. Nie utrzymujemy osobnych wersji logiki dla każdego narzędzia. Skille są częścią repozytorium; nie zostały zainstalowane globalnie na komputerze.

Narzędzie, które nie wczytuje instrukcji projektu automatycznie, można uruchomić z wiadomością:

> Przeczytaj AGENTS.md w katalogu projektu FB-manager i korzystaj z opisanych tam skilli. Obsługuj moje polecenia dotyczące kampanii przez lokalny silnik Python, a wyniki przedstawiaj w rozmowie.

Samo zainstalowanie pakietu Python nie dodaje instrukcji do dowolnej aplikacji czatu. Środowisko musi umieć odczytać projekt i uruchamiać narzędzia. W przyszłości ten sam silnik może być udostępniony przez MCP.

## Co działa obecnie

`capabilities` opisuje możliwości silnika. Demo zawiera 60 dni danych, dzięki czemu obsługuje raport 30-dniowy. `report campaigns` pokazuje wszystkie kampanie snapshotu, a `audit` zwraca rekomendacje wraz z zakresem sprawdzonych i niedostępnych danych. Prośby obejmujące kilka kont agent wykonuje osobno dla każdego konta.

Obecny audyt jest częściowy: dostępne są wyniki i lista kampanii. W demo są także profile celów; Meta wymaga jeszcze mapowania konwersji. Nie ma konfiguracji pomiaru, targetowania, kreacji, budżetów ani historii zmian. Agent ma obowiązek to powiedzieć. Podłączone konta korzystają z API Meta i osobnej bazy danych. Demo nie zastępuje rzeczywistych danych.

## Dalszy rozwój

Adapter Meta już dostarcza rzeczywiste wyniki. Kolejne rozszerzenia obejmą mapowanie konwersji, pomiar, strukturę zestawów, kreacje i budżety. Dopiero wtedy będzie możliwy pełniejszy audyt konta i przygotowywanie zweryfikowanych planów zmian.
