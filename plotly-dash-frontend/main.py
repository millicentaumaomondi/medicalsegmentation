from app import api_url
from dash import html, Input, Output, callback, dcc, State, ctx
from dash.exceptions import PreventUpdate
import base64
import dash_bootstrap_components as dbc
import io
import os
import requests
import shutil
import uuid
import zipfile

upload_message = 'Multiple file uploads are allowed. Please place all scans in a folder, select all files, and upload them together. Files should be of type png, jpg or jpeg.'
seg_success_msg = "Segmentation successful. Output files downloaded and saved as 'segmented scans.zip'."
UPLOAD_DIRECTORY = 'uploads'


def create_zip(file_data_list, filenames):
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        for data, name in zip(file_data_list, filenames):
            decoded_data = base64.b64decode(data.split(',')[1])
            zf.writestr(name, decoded_data)
    memory_file.seek(0)
    return memory_file


layout = html.Div(style={'padding-top': '30px', 'background-image': 'url("/assets/brain_imag_bg.webp"',
                         'height': '100vh'}, children=[
dcc.ConfirmDialog(
                id='segment_output', submit_n_clicks=0,
                message='Segmentation successful. Output files downloaded.',
            ),
    dbc.Row(children=[
        dbc.Col(children=[
            html.H2("BRAIN IMAGE TUMOR SEGMENTATION", className="text-center mb-4",
                    style={'textAlign': 'center', 'font-weight': 'bold', 'color': 'red', 'padding-top': '10px',
                           'font-size': '200%'}),
        ], width=11),
        dbc.Col(dbc.Button(id='logout', children='Logout', n_clicks=None))], justify='center'),
    dbc.Container(style={'padding-top': '100px'}, children=[
        dbc.Row(children=[
            dbc.Col(children=[
                dbc.Card([
                    dbc.CardBody(style={'background-color': 'GhostWhite'}, children=[
                        dbc.Label("Upload Folder", html_for="upload-files"),
                        dbc.Card([
                            dbc.CardBody(style={'textAlign': 'center', }, children=[
                                dcc.Upload(id='upload-files',
                                           children=html.Div([
                                               'Drag and Drop or ', html.A('Select Files')]),
                                           multiple=True,
                                           style={'width': '100%', 'height': '60px',
                                                  'lineHeight': '60px', 'borderWidth': '1px',
                                                  'borderStyle': 'dashed', 'borderRadius': '5px',
                                                  'textAlign': 'center',
                                                  'font-family': 'Lucida Console'}),
                        html.Em(upload_message, style={'color': '#1d3557', 'padding-top': '15px',
                                                       'padding-bottom': '15px'}),
                            ])]),
                        html.Br(),
                        html.Em(id='num_uploads', children='You have uploaded no file',
                                style={'font-family': 'Lucida Console', 'text-color': 'red', 'textAlign': 'center'}),
                        html.Br(),
                        html.Br(),
                        dbc.Row(children=[dbc.Col(children=[
                            dbc.Button("Segment Scans", id='segment', color="danger", className='text-center',
                                       outline=True, size='md',
                                       style={'padding-left': '45px', 'padding-right': '45px', }),
                            dcc.Loading(dcc.Download(id='download-btn'), fullscreen=True, ),
                            html.Br(),
                        ],
                            width={'offset': 4}, style={'padding-left': '25px', 'padding-right': '15px',
                                                        'padding-top': '10px', 'padding-bottom': '10px'})],
                            justify="center"),
                    ], ),
                ], ),
            ], width={'size': 6, 'offset': 3})]),
    ], fluid=True)])


@callback(Output('num_uploads', 'children'),
          Input('upload-files', 'contents'),
          State('upload-files', 'filename'))
def count_uploads(contents, file_names):
    if not file_names:
        raise PreventUpdate
    if file_names is None:
        return 'You have uploaded no file'

    num_files = len(file_names)
    if num_files == 1:
        return f"You have uploaded {num_files} file. Click 'Segment files' to proceed and download segmented images."
    else:
        return f"You have uploaded {num_files} files. Click 'Segment files' to proceed and download segmented images."


@callback(Output('url', 'pathname'),
          Output('token', 'data'),
          Output('logout', 'n_clicks'),
          Input('logout', 'n_clicks'),
          prevent_initial_callback=True)
def log_out(n_clicks):
    if n_clicks is None:
        raise PreventUpdate
    print(n_clicks, 'logout clicked')
    if n_clicks and ctx.triggered_id == 'logout':
        return '/', None, None


@callback(Output('download-btn', 'data'),
          Output('segment', 'n_clicks'),
          Output('segment_output', 'message'),
          Output('segment_output', 'displayed'),
          Input('upload-files', 'filename'),
          Input('upload-files', 'contents'),
          Input('token', 'data'),
          Input('segment', 'n_clicks'))
def segment_images(file_names, file_contents, bearer_token, n_clicks):
    if not n_clicks or file_contents is None or file_names is None:
        raise PreventUpdate
    headers = {
        'Authorization': f"Bearer {bearer_token}"
    }
    segment_api = f"{api_url}/prediction"
    try:
        if n_clicks > 0 and file_contents is not None:
            folder_name = str(uuid.uuid4())
            folder_path = os.path.join(UPLOAD_DIRECTORY, folder_name)

            if not os.path.exists(folder_path):
                os.makedirs(folder_path)

            for i, content in enumerate(file_contents):
                content_type, content_string = content.split(',')
                decoded_file = base64.b64decode(content_string)

                with open(os.path.join(folder_path, file_names[i]), 'wb') as f:
                    f.write(decoded_file)

            zip_filename = f"{folder_name}.zip"

            with zipfile.ZipFile(zip_filename, 'w') as zf:
                for file_name in file_names:
                    zf.write(os.path.join(folder_path, file_name), file_name)
            shutil.rmtree(folder_path)

            try:
                with open(zip_filename, "rb") as zip_file:
                    files = {
                        "file": (zip_filename, zip_file, "application/zip")
                    }
                    response = requests.post(segment_api, headers=headers, files=files)
            except FileNotFoundError:
                return None, 0, f"Error: The file {zip_filename} does not exist.", True
            except Exception as e:
                return None, 0, f"There is an error: kindly check your internet connection and/or the file type uploaded.", True

            file_content = response.content
            content_disp = response.headers.get('Content-Disposition')
            fast_api_zip = content_disp.split('filename=')[1].strip('"')
            file_name = 'segmented scans.zip'
            os.remove(zip_filename)
            return dcc.send_bytes(file_content, file_name), 0, seg_success_msg,  True
        elif file_contents is None:
            return None, 0, 'No file uploaded. Upload a file(s) and try again.', True
    finally:
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)
        if os.path.exists(zip_filename):
            os.remove(zip_filename)
        if os.path.exists(fast_api_zip):
            os.remove(fast_api_zip)


# if __name__ == '__main__':
#     app.run_server(debug=True, port=8051)
