package autotest.common.table;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

public class MultipleListFilter extends ListFilter {
    protected int maxVisibleSize;
    
    public MultipleListFilter(String fieldName, int maxVisibleSize) {
        super(fieldName);
        this.maxVisibleSize = maxVisibleSize;
        select.setMultipleSelect(true);
    }

    public JSONValue getMatchValue() {
        JSONArray labels = new JSONArray();
        // skip first item ("all values")
        for (int i = 1; i < select.getItemCount(); i++) {
            if (select.isItemSelected(i)) {
                labels.set(labels.size(), 
                           new JSONString(getItemText(i)));
            }
        }
        return labels;
    }

    public boolean isActive() {
        return true;
    }

    public void setChoices(String[] choices) {
        super.setChoices(choices);
        int visibleSize = Math.min(select.getItemCount(), maxVisibleSize);
        select.setVisibleItemCount(visibleSize);
        select.setSelectedIndex(0);
    }
}
