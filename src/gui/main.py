import flet as ft

def main(page: ft.Page):
    page.title = "Smart Psychometric Assembler (SPA)"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20
    
    page.add(
        ft.Row(
            controls=[
                ft.Text("SPA System läuft!", style=ft.TextThemeStyle.HEADLINE_LARGE),
                ft.Icon(ft.icons.CHECK_CIRCLE, color="green", size=40)
            ],
            alignment=ft.MainAxisAlignment.CENTER
        )
    )

if __name__ == "__main__":
    ft.app(target=main)
