# Kreator kampanii od wersji 0.4

Kreator prowadzi operatora przez przygotowanie nowej kampanii: zbiera brief, odczytuje ofertę i zasoby, tworzy nazwy oraz dokładny plan operacji. Po akceptacji tego planu potrafi utworzyć kampanię, zestawy, kreacje i reklamy w Meta. Kampanie, zestawy i reklamy powstają jako **PAUSED**. Aktywacja i edycja istniejących obiektów nie należą do tego wykonawcy.

Obsługa odbywa się przez rozmowę z agentem. Skill `meta-ads-campaign-wizard` jest częścią paczki dla Codex, Claude Code i Antigravity. Python odpowiada za stan, walidację, obliczenia, nazwy i wywołania API. Agent czyta materiały, proponuje treści, zadaje pytania i przedstawia plan użytkownikowi.

## Zakres pierwszego wykonawcy

| Element | Obsługiwany zakres |
| --- | --- |
| Cele | Leady z formularza Meta lub strony, zakupy, rejestracje w witrynie, sprzedaż biletów z zakupem albo istniejącą konwersją pomocniczą |
| Struktura | Jedna kampania na brief, od 1 do 5 zestawów i od 1 do 10 reklam w zestawie |
| Kreacje | Pojedynczy obraz już dostępny na koncie, nowy tekst, nagłówek, opis i CTA |
| Odbiorcy | Kraje, zakres wieku 18–65+, bez szczegółowych zainteresowań i własnych grup |
| Umiejscowienia | Aktualności Facebooka; wybór musi być widoczny i zaakceptowany |
| Budżet | Dzienny albo całkowity, ustawiany na poziomie zestawów; PLN, EUR, USD lub GBP |
| Harmonogram | Jawny początek i koniec z przesunięciem strefy konta; początek w przyszłości |
| Zasoby | Istniejąca strona, obrazy, formularz, piksel i ewentualna konwersja niestandardowa |
| Kategorie szczególne | Brak obsługi w tym wykonawcy; pole musi być jawnie rozstrzygnięte jako pusta lista |
| API | v26.0; pozostałe wersje wymagają osobnej weryfikacji adaptera |

Ograniczenie do aktualności Facebooka i szerokich odbiorców jest zakresem technicznym tej wersji. Nie oznacza, że taki wybór jest najlepszy dla każdej kampanii. Operator może odrzucić wariant. Instagram, wideo, karuzele, katalogi, nowe formularze, upload obrazów i remarketing pozostają do dalszego wdrożenia. Kreator nie zastępuje brakującego zasobu przypadkowym materiałem.

## Przykład rozmowy

> Przygotuj kampanię leadową dla tego projektu. Chcemy promować konsultacje przez formularz Meta. Budżet to 100 zł dziennie przez dwa tygodnie.

Agent odczyta kontekst oraz istniejące cele. Sprawdzi ofertę, dostępne strony, obrazy i formularze. Uzupełni znane dane i zapyta o brakujące ustalenia. Po przygotowaniu treści oraz struktury pokaże dokładny plan. Dopiero wtedy użytkownik może zaakceptować jego wysłanie.

W późniejszej rozmowie można powiedzieć:

> Wróćmy do briefu konsultacji. Zmieńmy okres i pokaż, co musimy ponownie sprawdzić.

Stan pozostaje w `data/campaign-wizard.sqlite3`, osobno dla klienta i konta. Zmiany tworzą kolejne wersje. Poprzednie odpowiedzi, dowody, plany, akceptacje i wyniki operacji pozostają w bazie. Nie kopiujemy ich do wspólnego repozytorium narzędzia.

## Odpowiedzi i materiały

Każde pole ma wartość, stan, źródło, odwołanie do dowodu i czas zapisu. Rozróżniamy `discovered`, `confirmed`, `conflict` i `unavailable`. Brak pola oznacza informację jeszcze nieuzyskaną. Kreator zwraca najwyżej trzy pytania na rundę; agent formułuje je dla operatora zwykłym językiem.

Potwierdzenie techniczne obejmuje walutę i strefę. Budżet, harmonogram, ofertę, prawa do materiałów, pomiar, odbiorców i treści potwierdza operator. Fakty z witryny lub dokumentu zaczynają jako dane znalezione. Zmiana celu, strony lub sposobu pomiaru oznacza zależne pola jako wymagające ponownego rozstrzygnięcia.

`wizard website` pobiera jedną publiczną stronę HTTPS, wyciąga tytuł, opis, tekst, linki i adresy obrazów. Nie wykonuje JavaScript ani instrukcji z treści, nie wysyła formularzy, nie korzysta z cookies i nie loguje się. Pobranie ma limit 1 MB oraz ograniczoną liczbę przekierowań. Każde połączenie używa sprawdzonego publicznego IP przypisanego do hosta, co blokuje odczyty sieci lokalnej. Kolejne istotne podstrony wybiera agent. Niedostępność witryny nie jest zgodą na wymyślenie jej treści.

`wizard discover` zapisuje inwentaryzację dostępnych zasobów. Brak uprawnienia do jednego rodzaju zasobów ma osobny błąd i nie jest przedstawiany jako pusta, poprawnie odczytana lista. Po wyborze strony ponowny odczyt obejmuje jej formularze. Waluta i strefa uzupełniają brief automatycznie, o ile nie ma sprzecznego wcześniejszego ustalenia.

## Cel, struktura i plan

Przed planowaniem potrzebny jest zapisany cel z rejestru wersji 0.3. Brief wskazuje jego ID i konkretną wersję. Generator sprawdza projekt, walutę, dokładny klucz zdarzenia oraz rolę wyniku. Dla przekliknięcia do zakupu wymaga istniejącej konwersji niestandardowej przypisanej do wybranego piksela; nie obniża celu do kliknięcia reklamy. Sam odczyt piksela nie potwierdza działania zdarzenia. Gotowość pomiaru musi być sprawdzona przed potwierdzeniem briefu.

Python rezerwuje kody C, S i A atomowo w obrębie konta. Wznowienie tego samego planu zachowuje kody, a nowa wersja briefu otrzymuje nowe rezerwacje. Nazwy zawierają kody klienta, projektu, celu, rynku i lokalne klucze obiektów. Stałe oznaczenia UTM korzystają z kluczy C i A. Język w nazwie opisuje język reklamy; nie dodaje filtra językowego odbiorców.

Kwoty przeliczamy na jednostki API bez zaokrąglania: np. 50,25 PLN to 5025. Więcej niż dwa miejsca po przecinku blokuje plan. Suma obejmuje budżety zestawów jeden raz. Budżet dzienny opisuje ustawienie platformy, nie gwarantowany twardy limit wydatku każdego dnia. Na koncie nie występują wydatki z tych nowych obiektów, dopóki pozostają wstrzymane.

Plan zawiera cały brief, wersję celu, zasoby sprawdzone przez API, kwoty, daty, nazwy, treści i dokładne parametry każdej operacji. Każdy obiekt ma stan „przed: nie istnieje” oraz pełen stan żądany. Zależności między nowymi obiektami są wskazane przez lokalne klucze, zastępowane dopiero zweryfikowanymi ID z Meta. Plan otrzymuje SHA-256 i termin ważności: najwyżej 24 godziny, nie później niż planowany początek kampanii.

Podgląd Markdown jest czytelny lokalnie w narzędziu agenta. Operator powinien zobaczyć też wybrane obrazy. Adresy i wymiary są w odczycie zasobów; same hashe nie wystarczają do oceny kreacji. Ten podgląd nie zastępuje późniejszego sprawdzenia rzeczywistej reklamy na platformie.

## Akceptacja i domyślny odczyt

Istniejące konfiguracje pozostają `access_mode: read_only`. Po jawnej decyzji operatora o użyciu wykonawcy można zmienić **tylko to pole** w jego `config/local/meta-KLIENT.json` na `approved_create_paused`. Token musi mieć dostęp umożliwiający tworzenie reklam; rozszerzenie lokalnego trybu nie nadaje uprawnień w Meta. Nie dodawaj tokena do pliku briefu, parametrów CLI ani planu.

Po pokazaniu gotowego planu agent rejestruje rzeczywistą akceptację użytkownika przez `wizard approve`. Kontrakt wymaga identyfikacji operatora, treści jego zgody, odwołania do wiadomości i dokładnego hasha planu. Nie ma automatycznego zatwierdzania ani opcji `--yes`. Odpowiedzi na pytania i akceptacja briefu nie zastępują tej zgody. Jedna wyraźna decyzja może obejmować włączenie lokalnego wykonawcy i konkretny pokazany plan.

Zgodę można cofnąć tym samym poleceniem z `decision: revoke`. Wykonawca sprawdza ją przed uruchomieniem klienta API oraz ponownie przed każdym POST. Wersja briefu, hash, ważność, konto i sprawdzane zasoby muszą pozostać zgodne. Domyślne klienty analityczne nadal wykonują wyłącznie GET. Nie ma operacji usuwania, archiwizacji, aktywacji ani edycji istniejącego obiektu.

Rejestr przechowuje dowód zgody przekazany przez agenta. Nie uwierzytelnia kryptograficznie autora wiadomości. Poprawne powiązanie z rzeczywistą decyzją użytkownika jest obowiązkiem agenta, opisanym w skillu. Lokalny kod i SQLite nie ograniczają złośliwego programu mającego dostęp do tokena. Oddzielny serwis zatwierdzania i wykonawca z własnymi poświadczeniami byłyby kolejnym etapem izolacji.

## Wykonanie i przerwanie

Każda operacja zapisuje zamiar wysłania, zwrócone ID i wynik odczytu kontrolnego. Sprawdzamy konto i parametry zaakceptowane w planie, dopuszczając dodatkowe pola techniczne zwrócone przez platformę. Równoległy wykonawca w tej samej przestrzeni konta jest blokowany. Przed tworzeniem sprawdzamy również, czy nazwa już występuje na koncie.

Po pełnym sukcesie nowa kampania dostaje lokalne przypisanie do celu i wersji z briefu. Początek obowiązywania wynika z daty planowanego startu. Ten zapis nie aktywuje kampanii. Jeżeli lokalne przypisanie nie powiedzie się, wynik operacji Meta pozostaje w dzienniku; należy sprawdzić `wizard status`, zanim ponowi się pracę.

Przy błędzie lub niepewnej odpowiedzi wynik pozostaje częściowy. `wizard reconcile` tylko odczytuje stan: korzysta ze zwróconego ID lub szuka dokładnej nazwy w zakresie konta, a następnie porównuje parametry. Brak jednoznacznego dopasowania blokuje ponowne tworzenie. Nie resetujemy wówczas bazy ani nie kasujemy obiektów. Nawet jawne odrzucenie zapisu przez Meta wymaga sprawdzenia dziennika i przyczyny; wykonawca nie ponawia POST automatycznie.

Wznowienie poprawnie uzgodnionego, nadal zaakceptowanego planu pomija już zweryfikowane operacje. Jeśli wygasł plan, zmieniły się zasoby albo potrzebne są inne parametry, przygotuj odrębny zakres do akceptacji z uwzględnieniem istniejących obiektów. Obecny wykonawca nie naprawia ani nie aktywuje tych obiektów.

## Komendy dla agenta

Operator używa języka naturalnego. W przestrzeni klienta poniższe `meta-ads` zastępujemy przez `python3 workbench.py meta`.

```bash
meta-ads wizard start --client CLIENT --account ACCOUNT --project PROJECT
meta-ads wizard list --client CLIENT --account ACCOUNT
meta-ads wizard show --client CLIENT --account ACCOUNT --id DRAFT
meta-ads wizard answer --client CLIENT --account ACCOUNT --file context/answer.json
meta-ads wizard website --client CLIENT --account ACCOUNT --id DRAFT --url https://example.com/oferta
meta-ads wizard discover --client CLIENT --account ACCOUNT --id DRAFT
meta-ads wizard plan --client CLIENT --account ACCOUNT --id DRAFT --preview reports/plan.md
meta-ads wizard plan-show --client CLIENT --account ACCOUNT --plan-hash HASH
meta-ads wizard approve --client CLIENT --account ACCOUNT --file context/approval.json
meta-ads wizard execute --client CLIENT --account ACCOUNT --plan-hash HASH
meta-ads wizard status --client CLIENT --account ACCOUNT --plan-hash HASH
meta-ads wizard reconcile --client CLIENT --account ACCOUNT --plan-hash HASH
```

Zastąp oznaczenia rzeczywistymi identyfikatorami z wyników. Nie używaj fikcyjnych ID z przykładów na prawdziwym koncie. `expected_revision` w odpowiedzi pochodzi z ostatniego odczytu briefu. `wizard plan` wymaga aktualnego odczytu zasobów i nie jest komendą offline. `wizard show`, `answer`, `list`, `approve` i `status` nie wywołują Meta. Podglądy nie nadpisują istniejących plików.

Schematy `creation_brief`, `wizard_answer` i `wizard_approval` są dostępne przez `schema export` oraz w `schemas/`. Przykłady w `examples/wizard/` są syntetyczne. Plik kompletnego briefu służy jako wzór; odpowiedzi przekazujemy do kreatora przez kontrakt `wizard_answer`.

## Weryfikacja adaptera

Kształt parametrów, endpointy tworzenia i odczytu zasobów sprawdzono w oficjalnym SDK Meta: [AdAccount](https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/adobjects/adaccount.py), [AdSet](https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/adobjects/adset.py), [AdCreative](https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/adobjects/adcreative.py) i [Campaign](https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/adobjects/campaign.py). Pola z SDK nie gwarantują dopuszczalności każdej kombinacji dla danego konta. Ostateczną walidację wykonuje Meta podczas tworzenia; lokalny preflight sprawdza dostępność wskazanych zasobów i zgodność wybranych parametrów.

Testy automatyczne obejmują rozmowę, zmiany zależności, plany dla obsługiwanych celów, sumy budżetów, zakres klienta, blokady zgód, utratę odpowiedzi, odczyt kontrolny i wznowienie bez dodatkowych obiektów. Wykorzystują symulowane API. Utworzenie pierwszej kampanii pilotażowej w Meta jest osobnym działaniem: wymaga konkretnego briefu i zaakceptowanego planu. Dodanie kreatora do kodu nie jest takim testem.

Każda decyzja akceptacji ma własne `approval_id` oraz `expected_revision` z ostatniego odczytu `wizard status` (0, gdy nie ma decyzji). Ponowienie starej zgody nie przywraca jej po cofnięciu. Nowa decyzja wymaga nowego ID i aktualnej wersji.
