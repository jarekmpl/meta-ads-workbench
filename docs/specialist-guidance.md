# Własne wytyczne specjalisty

System ma trzy osobne warstwy: wspólne metody narzędzia, osobiste wytyczne specjalisty i kontekst konkretnego klienta. Aktualizacja zmienia pierwszą z nich. Pozostałe należą do użytkownika.

| Warstwa | Co zawiera | Miejsce |
| --- | --- | --- |
| Narzędzie | Ogólne skille, kompendium, standardy i skrypty | `skills/`, `knowledge/`, `src/` oraz pozostałe pliki wydania |
| Specjalista | Własne metody analizy, praktyki testów, sposób formułowania rekomendacji | Osobny profil wskazany w `specialist.json` |
| Klient | Cele, strategię, ton marki, promocje, dane i ustalenia ze spotkań | `context/`, `projects/`, `data/` i raporty tego klienta |

Profil może służyć w kilku przestrzeniach klientów na tym samym komputerze. Przykładowa organizacja:

```text
MetaAds/
  specialists/
    anna/
      profile.json
      materials/
  clients/
    klient-a/
      specialist.json       wskazuje profil Anny
      context/
    klient-b/
      specialist.json       wskazuje ten sam profil Anny
      context/
```

Nie otwieraj wszystkich klientów jako jednego projektu. Podłączenie profilu daje dostęp tylko do jawnie wybranego katalogu ogólnych wytycznych, a nie do innych klientów. Profil nie powinien zawierać ich danych, nazw, ofert ani wyników. Kontrola ścieżek nie zastępuje sprawdzenia treści przez specjalistę. Wspólny profil jest lokalnym katalogiem, nie usługą synchronizacji między komputerami.

## Uruchomienie

Możesz powiedzieć agentowi: „Utwórz mój profil specjalisty, który będę stosować u różnych klientów”. Agent wykona:

```bash
python3 workbench.py specialist init --directory "$HOME/MetaAds/specialists/anna" --id anna --name "Anna"
```

W kolejnej przestrzeni tego samego specjalisty:

```bash
python3 workbench.py specialist attach --directory "$HOME/MetaAds/specialists/anna"
```

Alternatywnie `--directory specialist` tworzy profil wewnątrz bieżącej przestrzeni. Taki profil również przetrwa aktualizację, ale nie można podłączać go z katalogu innego klienta. Do pracy z wieloma klientami wybierz wspólny katalog poza ich przestrzeniami. Profil i jego pliki nie mogą być dowiązaniami.

## Dodawanie i aktualizowanie wytycznych

Powiedz np.: „Dodaj do moich wytycznych, że przed testem kreacji ustalamy hipotezę, miernik i kryterium zakończenia. Stosuj tę zasadę w analizach”. Agent zapisze treść w pliku Markdown, doda ją do profilu i oznaczy jako aktywną na podstawie tej dyspozycji.

```bash
python3 workbench.py specialist add --file specialist/inbox/testy.md --title "Przygotowanie testów" --topic experiments
python3 workbench.py specialist status --id ID_Z_WYNIKU --revision 1 --status active --reason "Specjalista polecił stosować tę zasadę w rozmowie"
python3 workbench.py specialist list --topic experiments
python3 workbench.py specialist read --id ID_Z_WYNIKU
```

Nie ma zamkniętego katalogu tematów. Podaj tytuł, temat i plik TXT lub Markdown w UTF-8 do 1 MB. Nowe wpisy mają status `draft`. Lista domyślnie pokazuje aktywne wytyczne; `--history` pokazuje wszystkie wersje.

Aby zmienić wytyczną, ponów `specialist add` z jej `--id` i nowym plikiem. System dopisze rewizję. Stara pozostaje aktywna do chwili aktywacji nowej; wtedy przechodzi do historii. Wycofanie przez `specialist status --status retired` także zachowuje treść. Każda wersja ma SHA-256, a decyzje mają autora, datę i uzasadnienie. Ręczna zmiana pliku materiału powoduje błąd integralności.

## Stosowanie podczas pracy

Agent odczytuje pasujące aktywne wytyczne za pomocą skilla meta-ads-specialist. Własne metody mają pierwszeństwo przed domyślnymi metodami narzędzia w zakresie, którego dotyczą. Nie mogą zmieniać faktów z danych, celów i ograniczeń klienta ani zasad bezpieczeństwa konta. Przy rzeczywistej rozbieżności agent pokazuje jej wpływ na decyzję.

W notatce analitycznej zapisuje profil, ID i rewizję wykorzystanej praktyki, jej hash, treść oraz sposób zastosowania. Ustalenia klienta zachowuje osobno w `context_basis`. Zmiana profilu nie przepisuje wcześniejszych notatek ani raportów.

Własnych wytycznych nie dopisuj bezpośrednio do AGENTS.md, skillów i kompendium narzędzia. Te pliki są aktualizowane centralnie. Jeżeli chcesz udostępnić metodę wszystkim specjalistom, przygotuj osobny wkład do wspólnej bazy. Sam zapis w profilu niczego nie publikuje.

## Kopie i zmiana operatora

W kopii klienta zachowaj `specialist.json`; wspólny profil kopiuj osobno w całości, razem z `profile.json` i `materials/`. Na innym komputerze podłącz jego rzeczywistą ścieżkę przez `specialist attach`. Sam wskaźnik nie kopiuje materiałów. Nowy operator podłącza własny profil i rozpoczyna nową rozmowę; nie modyfikuje profilu poprzednika. Uprawnienia systemowe do katalogów nadal ustala właściciel komputera.
