# Zasady zmian na kontach Meta

Ustalone przez użytkownika 10 września 2026. Obowiązują wszystkie konta, klientów, agentów i interfejsy projektu. Konfiguracja klienta ani polityka automatyzacji nie mogą ich osłabić.

## Zakaz kasowania

System nigdy nie usuwa niczego z konta: kampanii, zestawów, reklam, kreacji, materiałów ani innych obiektów i konfiguracji. Zakaz obejmuje także status `DELETED`, usuwanie w operacjach zbiorczych i sprzątanie po częściowo nieudanym wykonaniu. Nie wolno obchodzić go przez przeglądarkę, inny skrypt lub konektor. Akceptacja planu nie zezwala na usuwanie. Wstrzymanie lub archiwizacja są osobnymi zmianami i wymagają akceptacji; nie należy ich wykonywać samodzielnie jako zamiennika kasowania.

## Akceptacja każdej zmiany

1. Przygotuj lokalny plan: klient i konto, identyfikatory lub nazwy tworzonych obiektów, dokładne operacje, wartości przed/po, budżet, status i uzasadnienie.
2. Pokaż gotowy plan użytkownikowi. Wymagana jest jego wyraźna akceptacja tego zakresu przed pierwszym zapisem na koncie. Jeden plan może obejmować kilka dokładnie wymienionych zmian.
3. Zapisz dowód akceptacji powiązany z wersją i skrótem planu. Agent nie może wystawić zgody we własnym imieniu. Ogólne polecenie „optymalizuj”, uprzednia zgoda na automatyzację i milczenie nie są akceptacją planu.
4. Przed wykonaniem sprawdź zakres, ważność i bieżący stan. Zmiana planu lub istotnego stanu wymaga nowej akceptacji. Ważna zgoda na niezmieniony plan nie wymaga powtarzania pytania.
5. Wykonaj wyłącznie zaakceptowane operacje, zapisz ich wyniki i odczytaj stan kontrolny. Po niepewnym wyniku najpierw sprawdź stan; nie ponawiaj zapisu w ciemno. Dodatkowa naprawa lub cofnięcie ustawień wymaga własnego zaakceptowanego planu. Nigdy nie sprzątaj przez usuwanie.

Dotyczy to także tworzenia obiektów wstrzymanych, publikacji, aktywacji, pauzowania, archiwizacji, zmiany budżetu, harmonogramu, odbiorców, kreacji, pomiaru i uprawnień. Zgoda jest konieczna również przy zapisie niewywołującym wydatków.

## Stan wdrożenia

Obecny silnik obsługuje wyłącznie odczyt Meta. Oba klienty API wysyłają GET, ograniczają ścieżki i blokują parametry zmiany metody oraz operacji zbiorczych. `capabilities` udostępnia te zasady agentom. Obsługa planów, dowodów akceptacji i wykonawcy zapisu pozostaje do wdrożenia; do tego czasu także zaakceptowane zmiany nie są wykonywane przez silnik.

Przyszły wykonawca musi odrzucać usuwanie bezwarunkowo, a pozostałe zapisy bez ważnej zgody na dokładny plan — przed wysłaniem żądania. Testy muszą sprawdzać brak wywołania sieci dla usuwania, brakującej zgody, obcego konta, zmienionego planu, wygaśnięcia, cofnięcia zgody i konfliktu stanu. Nie może istnieć opcja omijająca te kontrole. Mocniejsza izolacja wymaga osobnego wykonawcy z poświadczeniami zapisu; instrukcje i lokalny kod nie ograniczają technicznie innych programów mających dostęp do tokena.

Odczyty, analizy, raporty i lokalne propozycje mogą działać automatycznie. Zasady nie zakazują zwykłych lokalnych prac nad projektem.
