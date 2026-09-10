# Zacznij tutaj

Ten instalator przygotowuje osobną przestrzeń pracy dla jednego klienta. Zawiera silnik Python, skille, kompendium Meta Ads i eksport PDF Bluerank. Nie wymaga klucza API do LLM: korzystasz z zalogowanego Codex, Claude Code albo Antigravity, które mają dostęp do plików i terminala. Dostęp do Meta konfigurujesz osobno.

## 1. Przygotuj komputer

Potrzebujesz macOS, Linux albo Windows z WSL oraz Pythona 3.11 lub nowszego. Sprawdź w terminalu:

```bash
python3 --version
```

Jeśli wersja jest starsza, zainstaluj aktualny Python ze strony [python.org](https://www.python.org/downloads/) lub przez zatwierdzone narzędzie firmowe. Na Windows wykonuj dalsze kroki w WSL i trzymaj katalog klienta w jego systemie plików. Instalator nie obsługuje natywnego Windows.

## 2. Pobierz paczkę

Na GitHubie wybierz **Code → Download ZIP** i rozpakuj archiwum. Możesz też sklonować repozytorium. Katalog instalatora służy do zakładania przestrzeni klientów; nie umieszczaj w nim ich danych ani raportów.

Otwórz terminal w rozpakowanym katalogu i uruchom:

```bash
python3 install.py
```

Instalator zapyta o kod klienta, nazwę, preferowane narzędzie i katalog docelowy. Zaproponuje `~/MetaAds/clients/KOD`. Kod jest stały, np. `klient-a`; używaj małych liter bez polskich znaków. Każdy klient musi mieć własny katalog poza repozytorium instalatora i poza innymi klientami.

Instalator skopiuje wyłącznie pliki z wykazu wydania, utworzy prywatne katalogi, zainstaluje zależności z `uv.lock` i sprawdzi środowisko. Jeżeli nie ma `uv`, zainstaluje jego przypiętą wersję w lokalnym `.bootstrap/`. Nie instaluje aplikacji LLM ani nie loguje operatora do Meta. Pierwszy start wymaga internetu do pobrania zależności i ewentualnie Pythona.

Wariant bez pytań, przydatny dla administratora:

```bash
python3 install.py --client klient-a --name "Klient A" --agent codex --destination "$HOME/MetaAds/clients/klient-a"
```

Po błędzie pobierania zależności użyj tego samego instalatora z `--resume`:

```bash
python3 install.py --resume --destination "$HOME/MetaAds/clients/klient-a"
```

Wznowienie instaluje zależności. Nie zastępuje kodu, kontekstu ani konfiguracji istniejącego klienta. Nie jest mechanizmem aktualizacji wersji.

## 3. Otwórz klienta w wybranym narzędziu

Otwórz **katalog wskazany na końcu instalacji**, np. `~/MetaAds/clients/klient-a`, jako osobny projekt. Nie otwieraj nadrzędnego folderu ze wszystkimi klientami. Nie kontynuuj rozmowy innego klienta.

- **Codex:** dodaj katalog klienta jako projekt i rozpocznij nową rozmowę. Wspólną instrukcją jest `AGENTS.md`.
- **Claude Code:** uruchom Claude Code w katalogu klienta. `CLAUDE.md` odsyła do wspólnej instrukcji. Instalator wyłącza automatyczną pamięć w ustawieniach tej przestrzeni; trwałe ustalenia zapisujemy w `context/`.
- **Antigravity:** otwórz katalog klienta. W ustawieniach reguł przestrzeni sprawdź plik `meta-ads.md` i ustaw **Always On**. Instalator umieszcza go w `.agents/rules/`; jeśli dana wersja aplikacji go nie wykryje, dodaj regułę przez panel Customizations → Rules → Workspace i wklej zawartość `adapters/antigravity.md`.

W każdym narzędziu wyślij tę samą wiadomość:

> Przeczytaj AGENTS.md, sprawdź przestrzeń klienta i przeprowadź mnie krok po kroku przez pierwsze uruchomienie. Pytaj o brakujące informacje i wykonuj samodzielnie dostępne odczyty. Nie proś mnie o wklejanie tokenów do rozmowy.

Agent powinien podać nazwę klienta, potwierdzić tryb odczytu i wskazać następny krok. Jeżeli tego nie robi, odwołaj się wprost do `skills/meta-ads-onboarding/SKILL.md`.

## 4. Podłącz konto Meta

Agent pomoże ustalić, czy masz aplikację Marketing API, dostęp do konta i właściwe uprawnienia. Szczegóły są w [instrukcji Meta](docs/meta-setup.md). Żadna aplikacja LLM nie nadaje sama dostępu do kont reklamowych.

W terminalu klienta uruchom:

```bash
python3 workbench.py onboard
```

Kreator zapyta o numer konta, ID aplikacji, wersję API z panelu Meta i opcjonalne portfolio. Token wpisz dopiero w osobnym, ukrytym polu terminala:

```bash
python3 workbench.py meta auth store-token --client klient-a
```

Przy App Secret Proof dodaj `--with-app-secret`. Poświadczenia pozostają w `secrets/`, poza Gitem. Następnie poproś agenta:

> Sprawdź połączenie i pobierz raport za ostatnie 30 pełnych dni.

Puste wyniki przy braku emisji nie oznaczają błędnej instalacji. Przy wygasłym tokenie agent wskaże potrzebę odnowienia. Nie przełączy się na dane demonstracyjne.

## 5. Dodaj kontekst i zacznij pracę

Powiedz np.:

> Dodaj tę notatkę ze spotkania do kontekstu klienta. Te ustalenia dotyczą wyłącznie jesiennej promocji.

Możesz przekazać tekst w rozmowie albo umieścić plik w `context/inbox/`. Nie musisz uzupełniać brandbooka, strategii ani całej listy pól. Dodawaj to, co jest przydatne. Agent zarejestruje materiał, ustali zakres i wyjaśni ewentualny konflikt z wcześniejszymi ustaleniami.

Dalsza praca: [codzienny proces specjalisty](docs/operator-workflow.md). Możliwości i ograniczenia: [README](README.md).

## Gdy coś nie działa

Uruchom `python3 workbench.py doctor`. Wynik sprawdza lokalne zależności i stan konfiguracji, nie wykonuje testu API. Podaj agentowi komunikat błędu bez tokena. Brak `ffmpeg` ogranicza przygotowanie kadrów wideo; nie blokuje raportów ani PDF. Instalator nie dodaje tego narzędzia systemowego.

Źródła instrukcji integracji: [Codex — AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md), [Claude Code — pamięć projektu](https://code.claude.com/docs/en/memory), [Antigravity — reguły przestrzeni](https://antigravity.google/docs/rules-workflows), [uv — instalacja](https://docs.astral.sh/uv/getting-started/installation/). Wspólne skille są czytane z plików projektu; nie zakładamy jednakowej obsługi instalacji pluginów w tych narzędziach.

## Kreator kampanii 0.4

[Instrukcja kreatora](docs/campaign-wizard.md) opisuje przygotowanie nowej kampanii w rozmowie, zapis stanu i kontrolowane tworzenie nowych obiektów PAUSED. Skorzystaj ze skilla meta-ads-campaign-wizard. Zgody, briefy i dziennik w data/campaign-wizard.sqlite3 należą do danych klienta i powinny być objęte kopią zapasową. Pierwsza instalacja zachowuje tryb read_only.

## Praca z dokumentami

Po dodaniu materiałów możesz poprosić: „Które zasady komunikacji obowiązują w tej promocji?” albo „Porównaj dwa ostatnie spotkania”. Agent odczyta dokumenty i pokaże konkretne ustalenia oraz ewentualne sprzeczności. Korzysta ze skilla meta-ads-context; [opis procesu](docs/client-context.md) wyjaśnia zakres odczytu i zapis podstaw rekomendacji.

## Własne wytyczne i kolejne wersje

Powiedz agentowi: „Utwórz mój profil specjalisty” i dodawaj do niego własne metody bez danych klientów. Ten sam profil można podłączyć do kilku przestrzeni. [Proces profilu](docs/specialist-guidance.md) opisuje wersje i aktywację wytycznych.

Do aktualizacji korzystaj z update.py, a nie ponownej instalacji na istniejący katalog. [Instrukcja aktualizacji](docs/updating.md) obejmuje także starsze instalacje, zachowanie danych i odzyskanie po przerwaniu procesu.
