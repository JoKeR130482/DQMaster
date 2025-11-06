import pandas as pd

def create_excel():
    """Создает корректный Excel-файл для тестирования."""
    data = {'Email': ['test@example.com', 'invalid-email', 'test@company.ru', '']}
    df = pd.DataFrame(data)

    output_path = 'test_emails.xlsx'
    # index=False, чтобы не добавлять столбец с индексами в Excel
    df.to_excel(output_path, index=False, engine='openpyxl')
    print(f"Файл '{output_path}' успешно создан.")

if __name__ == "__main__":
    create_excel()
