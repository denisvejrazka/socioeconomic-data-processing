# načtení potřebných knihoven
import pandas as pd
import pymongo
import matplotlib.pyplot as plt

# inicializace spojení s klientem a tabulky
client = pymongo.MongoClient("mongodb://localhost:27017")
db = client["socioecon"]
foreigners = db["foreigners"]
gdp = db["gdp"]

# vložení dat foreigners do databáze
def insert_foreigners():
    # přečtení dat csv
    df_foreigners = pd.read_csv("D:\data.CSV")
    foreigners = db["foreigners"]
    df_foreigners = df_foreigners.where(pd.notnull(df_foreigners), None)

    # Převod na slovníky a vložení do MongoDB
    records = df_foreigners.to_dict(orient="records")
    foreigners.drop()
    foreigners.insert_many(records)


# vložení dat gdp do databáze
def insert_gdp():
    url = "https://cs.wikipedia.org/wiki/Seznam_st%C3%A1t%C5%AF_sv%C4%9Bta_podle_HDP_na_obyvatele"
    tables = pd.read_html(url)
    df_gdp = tables[0]

    df_gdp = df_gdp[["Stát", "2021"]]
    df_gdp.columns = ["country", "gdp_per_capita"]

    # cleanup
    df_gdp.loc[:, "gdp_per_capita"] = (
        df_gdp["gdp_per_capita"]
        .astype(str)
        .str.replace(r"[^\d]", "", regex=True)  # odstraní mezery, pomlčky apod.
    )

    # Převod na čísla
    df_gdp.loc[:, "gdp_per_capita"] = pd.to_numeric(df_gdp["gdp_per_capita"], errors="coerce")

    # Odstranění neplatných záznamů
    df_gdp = df_gdp.dropna(subset=["gdp_per_capita"])
    df_gdp = df_gdp[df_gdp["gdp_per_capita"] > 0]

    gdp.delete_many({})
    gdp.insert_many(df_gdp.to_dict(orient="records"))

    print("Data o HDP byla úspěšně uložena do MongoDB.")

# structure
def output_first_docs():
    print(" ")
    print("Foreigners: ")
    print(foreigners.find_one())
    print(" ")
    print("HDP: ")
    print(gdp.find_one())
    print(" ")

output_first_docs()

def aggregate_data():
    pipeline = [
        # Spojení kolekce 'foreigners' a 'gdp' podle státního občanství
        {
            '$lookup': {
                'from': 'gdp',
                'localField': 'stobcan_txt',  # Tento field odpovídá 'country' ve 'gdp'
                'foreignField': 'country',
                'as': 'gdp_info'
            }
        },
        # Rozbalení seznamu 'gdp_info' do jednotlivých dokumentů
        {
            '$unwind': '$gdp_info'
        },

        # Seskupení dat podle roku a státního občanství
        {
            '$group': {
                '_id': {
                    'year': '$rok',  # Přidání roku
                    'citizenship': '$stobcan_txt'  # Seskupení podle občanství
                },
                'total_foreigners': {'$sum': '$hodnota'},  # Součet počtu cizinců
                'average_gdp': {'$avg': '$gdp_info.gdp_per_capita'}  # Průměrný HDP na hlavu
            }
        },
        # Seřazení podle roku a HDP na hlavu
        {
            '$sort': {
                '_id.year': 1,  # Seřazení podle roku vzestupně
                'average_gdp': -1  # Seřazení podle průměrného HDP sestupně
            }
        }
    ]
    
    # Spuštění agregace na kolekci 'foreigners'
    result = list(foreigners.aggregate(pipeline))
    
    # Příprava dat pro vizualizaci
    years = []
    citizenships = []
    avg_gdp = []
    
    for doc in result:
        years.append(doc['_id']['year'])
        citizenships.append(doc['_id']['citizenship'])
        avg_gdp.append(doc['average_gdp'])
    
    # Vytvoření DataFrame pro snadnější analýzu
    df = pd.DataFrame({
        'Year': years,
        'Citizenship': citizenships,
        'Average GDP': avg_gdp
    })
    
    return df

def visualize_data_bar(df):
    # Výběr top 5 občanství podle průměrného HDP
    top_citizenships = df.groupby('Citizenship')['Average GDP'].mean().nlargest(5).index
    filtered_df = df[df['Citizenship'].isin(top_citizenships)]
    
    # Pivotování dat pro stackovaný bar chart
    pivot_df = filtered_df.pivot(index='Year', columns='Citizenship', values='Average GDP')
    
    # Vykreslení stacked bar chart
    pivot_df.plot(kind='bar', stacked=True, figsize=(12, 7))
    
    plt.title("Průměrný HDP na hlavu podle roku a státního občanství (Top 5)")
    plt.xlabel("Rok")
    plt.ylabel("Průměrný HDP na hlavu")
    plt.legend(title="Státní občanství", bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.grid(True)
    plt.tight_layout()  # Pro lepší zarovnání s legendou
    plt.show()


visualize_data_bar(aggregate_data())
