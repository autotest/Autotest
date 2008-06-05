package afeclient.client;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.user.client.DOM;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.KeyboardListener;
import com.google.gwt.user.client.ui.RootPanel;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.Widget;



public abstract class DetailView extends TabView {
    protected static final String NO_OBJECT = "";
    
    protected JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
    protected TextBox idInput = new TextBox();
    protected Button idFetchButton = new Button("Go");
    
    protected abstract String getNoObjectText();
    protected abstract String getFetchControlsElementId();
    protected abstract String getDataElementId();    
    protected abstract String getTitleElementId();
    protected abstract String getObjectId();
    protected abstract void setObjectId(String id); // throws IllegalArgumentException
    protected abstract void fetchData();
    
    public void initialize() {
        resetPage();
        
        RootPanel.get(getFetchControlsElementId()).add(idInput);
        RootPanel.get(getFetchControlsElementId()).add(idFetchButton);
        
        idInput.addKeyboardListener(new KeyboardListener() {
            public void onKeyPress(Widget sender, char keyCode, int modifiers) {
                if (keyCode == (char) KEY_ENTER)
                    fetchById(idInput.getText());
            }

            public void onKeyDown(Widget sender, char keyCode, int modifiers) {}
            public void onKeyUp(Widget sender, char keyCode, int modifiers) {}
        });
        idFetchButton.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                fetchById(idInput.getText());
            }
        });
    }

    protected void showText(String text, String elementId) {
        DOM.setInnerText(RootPanel.get(elementId).getElement(), text);
    }

    protected void showField(JSONObject object, String field, String elementId) {
        JSONString jsonString = object.get(field).isString();
        String value = "";
        if (jsonString != null)
            value = jsonString.stringValue();
        showText(value, elementId);
    }

    public void resetPage() {
        showText(getNoObjectText(), getTitleElementId());
        RootPanel.get(getDataElementId()).setVisible(false);
    }
    
    protected void updateObjectId(String id) {
        setObjectId(id);
        idInput.setText(id);
    }
    
    protected void fetchById(String id) {
        try {
            updateObjectId(id);
        }
        catch (IllegalArgumentException exc) {
            String error = "Invalid input: " + id;
            NotifyManager.getInstance().showError(error);
            return;
        }
        
        updateHistory();
        if (isVisible())
            refresh();
    }
    
    public void handleHistoryToken(String token) {
        if (token.equals(getObjectId()))
            return;
        try {
            updateObjectId(token);
        }
        catch (IllegalArgumentException exc) {
            return;
        }
    }
    
    public void refresh() {
        super.refresh();
        if (!getObjectId().equals(NO_OBJECT))
            fetchData();
    }
    
    public String getHistoryToken() {
        String token = super.getHistoryToken();
        String objectId = getObjectId();
        if (!objectId.equals(NO_OBJECT))
            token += "_" + objectId;
        return token;
    }
    
    protected void displayObjectData(String title) {
        showText(title, getTitleElementId());
        RootPanel.get(getDataElementId()).setVisible(true);
    }

}
